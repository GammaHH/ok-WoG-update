import os
import time

from ok import TriggerTask
from src.task.BaseWoGTask import BaseWoGTask
from ok.feature.Box import Box


class AutoStoreMergeSalvageTask(BaseWoGTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "\u81ea\u52d5\u5132\u5b58\u30fb\u5408\u6210\u30fb\u5206\u89e3"
        self.description = "偵測背包已滿後自動將物品存入倉庫；若存倉後背包仍滿，會接續嘗試自動合成綠色／藍色素材。"

        self.default_config = {
            "_enabled": False,
            "連續合成次數": 50,
        }

        self.config_description = {
            "連續合成次數":
                "設定存倉後背包仍滿時，最多可連續自動合成幾次。僅會處理綠色／藍色素材；偵測到空位或其他顏色時會立即停止。",
        }

        # DEBUG：先 1 秒；正式使用可改成 60.0
        self.trigger_interval = 10.0

        # 倉庫操作等待時間
        self.input_delay = 1.0

        # 合成一般操作間隔
        self.synthesis_action_delay = 1.0


        # 合成安全設定
        self.color_tolerance = 5

        # 空位色不能只靠「有任何 1 pixel 命中」。
        # 兩張實機畫面差距很大，因此改成比例門檻。
        # 0.001 = 0.1%
        self.empty_ratio_threshold = 0.005
        self.max_synthesis_rounds = 20

        # Local smoke-test flag:
        #   $env:WOG_FORCE_STORE = "1"
        # Forces one store -> synthesis cycle per process, then disables itself.
        self._force_store_consumed = False


    def get_max_synthesis_rounds(self):
        config = getattr(
            self,
            "config",
            {}
        )

        try:
            rounds = int(
                config.get(
                    "連續合成次數",
                    self.max_synthesis_rounds
                )
            )
        except (
            TypeError,
            ValueError
        ):
            rounds = self.max_synthesis_rounds

        return max(
            1,
            rounds
        )

    @property
    def force_store_test(self):
        value = os.environ.get("WOG_FORCE_STORE", "")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    # =========================================================
    # Common
    # =========================================================

    def input_wait(self):
        if self.input_delay > 0:
            self.sleep(self.input_delay)

    def full_screen_box(self):
        return Box(
            0,
            0,
            self.width,
            self.height
        )

    def find_fullscreen(
        self,
        name,
        threshold=0.80
    ):
        return self.find_one(
            name,
            box=self.full_screen_box(),
            threshold=threshold
        )

    # =========================================================
    # Anchor
    # =========================================================

    def find_menu_anchor(self):
        menu = self.find_fullscreen(
            "menu",
            threshold=0.80
        )

        if not menu:
            self.log_info("找不到 menu")
            return None

        return menu

    def get_ui_offset(self, menu):
        reference_menu = self.get_box_by_name("menu")

        dx = menu.x - reference_menu.x
        dy = menu.y - reference_menu.y

        return dx, dy

    def relative_box(
        self,
        name,
        dx,
        dy,
        padding=0
    ):
        ref = self.get_box_by_name(name)

        return Box(
            max(0, ref.x + dx - padding),
            max(0, ref.y + dy - padding),
            ref.width + padding * 2,
            ref.height + padding * 2,
            name=name
        )

    def find_relative(
        self,
        name,
        dx,
        dy,
        padding=30,
        threshold=0.80
    ):
        search_box = self.relative_box(
            name,
            dx,
            dy,
            padding
        )

        return self.find_one(
            name,
            box=search_box,
            threshold=threshold
        )

    # =========================================================
    # Detect "+"
    # =========================================================

    def detect_plus(
        self,
        dx,
        dy
    ):
        """
        用 depot_plus 圖片模板找「+」。
        不使用 OCR 辨識頁碼。
        """

        ref_1 = self.get_box_by_name("depot_page_1")
        ref_2 = self.get_box_by_name("depot_page_2")

        center_1_x = ref_1.x + ref_1.width / 2
        center_2_x = ref_2.x + ref_2.width / 2

        step_x = center_2_x - center_1_x

        if abs(step_x) < 1:
            self.log_info("depot_page_1 / depot_page_2 間距異常")
            return None

        first_x = ref_1.x + dx
        first_y = ref_1.y + dy

        # 從第 1 頁位置掃到畫面右側，只掃頁籤高度附近
        search_box = Box(
            max(0, int(first_x - 10)),
            max(0, int(first_y - 10)),
            max(1, self.width - int(first_x) + 10),
            ref_1.height + 20,
            name="depot_plus_search"
        )

        return self.find_one(
            "depot_plus",
            box=search_box,
            threshold=0.75
        )

    # =========================================================
    # Infer pages from page 1 / page 2
    # =========================================================

    def build_depot_pages(
        self,
        plus_box,
        dx,
        dy,
        max_pages=20
    ):
        """
        利用 depot_page_1、depot_page_2 的間距推導後續頁籤。
        depot_plus 所在格即為「新增頁面」，不會被點擊。
        """

        ref_1 = self.get_box_by_name("depot_page_1")
        ref_2 = self.get_box_by_name("depot_page_2")

        ref_1_center_x = ref_1.x + ref_1.width / 2
        ref_1_center_y = ref_1.y + ref_1.height / 2

        ref_2_center_x = ref_2.x + ref_2.width / 2
        ref_2_center_y = ref_2.y + ref_2.height / 2

        step_x = ref_2_center_x - ref_1_center_x
        step_y = ref_2_center_y - ref_1_center_y

        if abs(step_x) < 1:
            self.log_info("depot_page_1 / depot_page_2 間距異常")
            return []

        page_1_center_x = ref_1_center_x + dx
        page_1_center_y = ref_1_center_y + dy

        plus_center_x = plus_box.x + plus_box.width / 2

        plus_slot = int(
            round(
                (plus_center_x - page_1_center_x)
                / step_x
            )
        ) + 1

        if plus_slot <= 1:
            self.log_info("+ 的位置異常，停止操作")
            return []

        if plus_slot > max_pages + 1:
            self.log_info(f"+ 超出合理範圍：{plus_slot}")
            return []

        # + 本身是下一個新增格，因此有效頁數 = plus_slot - 1
        last_page = plus_slot - 1


        pages = []

        for page_number in range(
            1,
            last_page + 1
        ):
            offset_index = page_number - 1

            center_x = (
                page_1_center_x
                + step_x * offset_index
            )

            center_y = (
                page_1_center_y
                + step_y * offset_index
            )

            page_x = int(
                round(
                    center_x
                    - ref_1.width / 2
                )
            )

            page_y = int(
                round(
                    center_y
                    - ref_1.height / 2
                )
            )

            page_box = Box(
                max(0, page_x),
                max(0, page_y),
                ref_1.width,
                ref_1.height,
                name=f"depot_page_{page_number}"
            )

            pages.append(
                (
                    page_number,
                    page_box
                )
            )

        return pages

    # =========================================================
    # Wait depot ready
    # =========================================================

    def wait_depot_ready(
        self,
        dx,
        dy,
        timeout=5.0
    ):
        """
        點 depot 後最多等 5 秒。
        一旦找到 depot_plus，立即推導頁面。
        """

        end_time = time.time() + timeout

        while time.time() < end_time:
            plus_box = self.detect_plus(
                dx,
                dy
            )

            if plus_box:
                pages = self.build_depot_pages(
                    plus_box,
                    dx,
                    dy
                )

                if pages:
                    return pages

            self.sleep(0.25)

        self.log_info("5 秒內找不到 depot_plus")
        return []

    # =========================================================
    # Process depot pages
    # =========================================================

    def process_depot_pages(
        self,
        pages,
        dx,
        dy
    ):
        """
        依序：
        第 1 頁 → 背包到倉庫
        第 2 頁 → 背包到倉庫
        ...
        """

        for page_number, page_box in pages:
            self.click(page_box)
            self.input_wait()

            inv_in_depot = self.find_relative(
                "inv_in_depot",
                dx,
                dy,
                padding=80,
                threshold=0.80
            )

            if not inv_in_depot:
                self.log_info(
                    f"第 {page_number} 頁找不到 inv_in_depot"
                )
                continue


            self.click(inv_in_depot)
            self.input_wait()

        self.log_info("倉庫儲存完成")
        return True


    # =========================================================
    # Synthesis
    # =========================================================

    def synthesis_wait(self):
        """
        合成的一般操作間隔。
        """
        if self.synthesis_action_delay > 0:
            self.sleep(
                self.synthesis_action_delay
            )

    def get_anchor_offset(
        self,
        anchor,
        reference_name
    ):
        reference = self.get_box_by_name(
            reference_name
        )

        dx = anchor.x - reference.x
        dy = anchor.y - reference.y

        return dx, dy

    @staticmethod
    def make_color_range(
        rgb,
        tolerance=2
    ):
        r, g, b = rgb

        return {
            "r": (
                max(0, r - tolerance),
                min(255, r + tolerance)
            ),
            "g": (
                max(0, g - tolerance),
                min(255, g + tolerance)
            ),
            "b": (
                max(0, b - tolerance),
                min(255, b + tolerance)
            ),
        }

    def calculate_color_percentage_excluding(
        self,
        color,
        item_box,
        avoid_box
    ):
        """
        計算 synthesis_item 內指定顏色，
        但完全排除 synthesis_item_avoid。
        """

        item_left = item_box.x
        item_top = item_box.y
        item_right = item_box.x + item_box.width
        item_bottom = item_box.y + item_box.height

        avoid_left = max(
            item_left,
            avoid_box.x
        )
        avoid_top = max(
            item_top,
            avoid_box.y
        )
        avoid_right = min(
            item_right,
            avoid_box.x + avoid_box.width
        )
        avoid_bottom = min(
            item_bottom,
            avoid_box.y + avoid_box.height
        )

        # avoid 與 item 沒有交集
        if (
            avoid_left >= avoid_right
            or avoid_top >= avoid_bottom
        ):
            return self.calculate_color_percentage(
                color,
                item_box
            )

        regions = []

        # avoid 上方
        if avoid_top > item_top:
            regions.append(
                Box(
                    item_left,
                    item_top,
                    item_right - item_left,
                    avoid_top - item_top
                )
            )

        # avoid 下方
        if avoid_bottom < item_bottom:
            regions.append(
                Box(
                    item_left,
                    avoid_bottom,
                    item_right - item_left,
                    item_bottom - avoid_bottom
                )
            )

        middle_height = (
            avoid_bottom
            - avoid_top
        )

        # avoid 左側
        if (
            avoid_left > item_left
            and middle_height > 0
        ):
            regions.append(
                Box(
                    item_left,
                    avoid_top,
                    avoid_left - item_left,
                    middle_height
                )
            )

        # avoid 右側
        if (
            avoid_right < item_right
            and middle_height > 0
        ):
            regions.append(
                Box(
                    avoid_right,
                    avoid_top,
                    item_right - avoid_right,
                    middle_height
                )
            )

        total_area = 0
        matched_area = 0.0

        for region in regions:

            if (
                region.width <= 0
                or region.height <= 0
            ):
                continue

            area = (
                region.width
                * region.height
            )

            ratio = (
                self.calculate_color_percentage(
                    color,
                    region
                )
            )

            total_area += area
            matched_area += (
                ratio
                * area
            )

        if total_area <= 0:
            return 0.0

        return (
            matched_area
            / total_area
        )

    def classify_synthesis_item(
        self,
        item_box
    ):
        """
        只使用 synthesis_item 區域做顏色判定。

        綠：
            RGB (63, 113, 22) ±5

        藍：
            RGB (36, 79, 132) ±5

        empty：
            RGB (22, 21, 20) ±5

        規則：
            1. empty_ratio 達門檻 → 終止
            2. 否則有 green → 繼續
            3. 否則有 blue → 繼續
            4. 其他 → unsafe
        """

        green = self.make_color_range(
            (63, 113, 22),
            self.color_tolerance
        )

        blue = self.make_color_range(
            (36, 79, 132),
            self.color_tolerance
        )

        empty = self.make_color_range(
            (22, 21, 20),
            self.color_tolerance
        )

        green_ratio = self.calculate_color_percentage(
            green,
            item_box
        )

        blue_ratio = self.calculate_color_percentage(
            blue,
            item_box
        )

        empty_ratio = self.calculate_color_percentage(
            empty,
            item_box
        )

        if empty_ratio >= self.empty_ratio_threshold:
            result = "empty"
        elif green_ratio > 0:
            result = "green"
        elif blue_ratio > 0:
            result = "blue"
        else:
            result = "unsafe"

        # 保留辨識結果 log，移除其餘額外 debug log。
        self.log_info(
            "自動合成顏色判斷："
            f"green_ratio={green_ratio:.6f}, "
            f"blue_ratio={blue_ratio:.6f}, "
            f"empty_ratio={empty_ratio:.6f}, "
            f"result={result}"
        )

        return result

    def find_synthesis_tab_box(self):
        """
        synthesis / synthesis_on 只用來定位 tab。
        是否真的進入合成介面，由頁面內模板確認。
        """

        box = self.find_fullscreen(
            "synthesis_on",
            threshold=0.65
        )

        if box:
            return box

        return self.find_fullscreen(
            "synthesis",
            threshold=0.65
        )

    def synthesis_page_controls_visible(
        self,
        synthesis_box
    ):
        """
        autoadd_synthesis / synthesis_start 任一模板匹配成功，
        即視為已真正進入 synthesis 介面。
        """

        if not synthesis_box:
            return False

        synthesis_dx, synthesis_dy = (
            self.get_anchor_offset(
                synthesis_box,
                "synthesis_on"
            )
        )

        autoadd = self.find_relative(
            "autoadd_synthesis",
            synthesis_dx,
            synthesis_dy,
            padding=45,
            threshold=0.65
        )

        if autoadd:
            return True

        start = self.find_relative(
            "synthesis_start",
            synthesis_dx,
            synthesis_dy,
            padding=45,
            threshold=0.65
        )

        return bool(start)

    def detect_synthesis_state(self):
        """
        回傳：
            ("ready", box)   已確認在合成介面
            ("tab", box)     只找到 synthesis tab，尚未確認頁面
            ("unknown", None)
        """

        box = self.find_synthesis_tab_box()

        if not box:
            return "unknown", None

        if self.synthesis_page_controls_visible(
            box
        ):
            return "ready", box

        return "tab", box

    def wait_synthesis_on(
        self,
        timeout=5.0,
        synthesis_click_box=None
    ):
        """
        先判斷是否已在合成介面；只有尚未 READY 時才點 synthesis。
        最多嘗試約 5 秒。
        """

        end_time = time.time() + timeout

        while time.time() < end_time:
            state, synthesis_box = (
                self.detect_synthesis_state()
            )

            if (
                state == "ready"
                and synthesis_box
            ):
                return synthesis_box

            if synthesis_click_box:
                self.click(
                    synthesis_click_box
                )
                self.synthesis_wait()
            else:
                self.sleep(0.25)

        self.log_info(
            "合成失敗：5 秒內未確認 synthesis 頁面控制項"
        )
        return None

    def wait_synthesis_off(
        self,
        timeout=5.0
    ):
        """
        合成頁面控制項消失，即視為已退出 synthesis。
        """

        end_time = time.time() + timeout

        while time.time() < end_time:
            state, _box = (
                self.detect_synthesis_state()
            )

            if state != "ready":
                return True

            self.sleep(0.25)

        return False

    def exit_synthesis(self):
        """
        合成終止方式與 Train 相同：

            synthesis ON
            → 再點一次 synthesis tab
            → synthesis OFF

        不再點 menu。
        """

        state, synthesis_box = (
            self.detect_synthesis_state()
        )

        # 已經不是 ON，就不需要再做任何退出操作。
        if state != "ready":
            return True

        if not synthesis_box:
            self.log_info(
                "合成終止，但找不到 synthesis tab"
            )
            return False

        self.click(
            synthesis_box
        )

        self.synthesis_wait()

        if self.wait_synthesis_off(
            timeout=5.0
        ):
            return True

        self.log_info(
            "合成終止：點擊 synthesis tab 後仍未確認退出"
        )
        return False

    def synthesis_loop(
        self,
        synthesis_dx,
        synthesis_dy
    ):
        autoadd_box = self.relative_box(
            "autoadd_synthesis",
            synthesis_dx,
            synthesis_dy
        )

        item_box = self.relative_box(
            "synthesis_item",
            synthesis_dx,
            synthesis_dy
        )

        start_box = self.relative_box(
            "synthesis_start",
            synthesis_dx,
            synthesis_dy
        )

        max_rounds = (
            self.get_max_synthesis_rounds()
        )

        for round_number in range(
            1,
            max_rounds + 1
        ):
            # 第一次 Auto Add
            self.click(
                autoadd_box
            )
            self.synthesis_wait()

            # 第二輪起 Auto Add 點兩次
            if round_number >= 2:
                self.click(
                    autoadd_box
                )
                self.synthesis_wait()

            state = self.classify_synthesis_item(
                item_box
            )

            if state == "empty":
                self.log_info(
                    "自動合成終止：偵測到空位色"
                )
                self.exit_synthesis()
                return True

            if state not in (
                "green",
                "blue"
            ):
                self.log_info(
                    "自動合成終止：偵測到非綠 / 非藍狀態"
                )

                self.exit_synthesis()
                self.log_info(
                    "自動合成本輪結束：等待下一次 Backpack_full 檢查"
                )
                return False

            self.click(
                start_box
            )
            self.synthesis_wait()

        self.log_info(
            f"自動合成終止：達到連續合成上限 {max_rounds} 次"
        )
        self.exit_synthesis()
        return False

    def auto_synthesis(self):
        """
        此函式不自行判斷 Backpack_full。
        仍只由 auto_store 在「倉庫處理完成後仍 Backpack_full」
        時呼叫。

        進入後先確認是否真的已在 synthesis 介面；
        若未進入才導航 / 點擊 synthesis。
        """

        state, synthesis_box = (
            self.detect_synthesis_state()
        )

        if state == "ready":
            synthesis_on = synthesis_box
        else:
            menu = self.find_menu_anchor()

            if not menu:
                return False

            menu_dx, menu_dy = (
                self.get_ui_offset(
                    menu
                )
            )

            synthesis = self.find_relative(
                "synthesis",
                menu_dx,
                menu_dy,
                padding=40,
                threshold=0.70
            )

            if not synthesis:
                self.click(
                    menu
                )
                self.synthesis_wait()

                # menu 展開後再確認一次，避免已經在頁面卻重複點 toggle。
                state, synthesis_box = (
                    self.detect_synthesis_state()
                )

                if state == "ready":
                    synthesis_on = synthesis_box
                else:
                    synthesis = self.find_relative(
                        "synthesis",
                        menu_dx,
                        menu_dy,
                        padding=50,
                        threshold=0.70
                    )

            if state != "ready":
                if not synthesis:
                    synthesis = self.find_synthesis_tab_box()

                if not synthesis:
                    self.log_info(
                        "合成失敗：找不到 synthesis"
                    )
                    return False

                synthesis_on = (
                    self.wait_synthesis_on(
                        timeout=5.0,
                        synthesis_click_box=synthesis
                    )
                )

                if not synthesis_on:
                    return False

        synthesis_dx, synthesis_dy = (
            self.get_anchor_offset(
                synthesis_on,
                "synthesis_on"
            )
        )

        return self.synthesis_loop(
            synthesis_dx,
            synthesis_dy
        )


    # =========================================================
    # Main
    # =========================================================

    def run(self):
        self.auto_store()

    def auto_store(self):

        force_store = self.force_store_test and not self._force_store_consumed

        if force_store:
            self._force_store_consumed = True
            backpack_full = True
            self.log_info(
                "WOG_FORCE_STORE=1：跳過第一次 Backpack_full，強制進入一次存倉測試"
            )
        else:
            # 正常模式：Backpack_full 是唯一啟動條件。
            backpack_full = self.find_fullscreen(
                "Backpack_full",
                threshold=0.80
            )

        if not backpack_full:
            return

        self.log_info(
            "觸發自動儲存：Backpack_full"
        )

        menu = self.find_menu_anchor()

        if not menu:
            return

        dx, dy = self.get_ui_offset(
            menu
        )

        depot = self.find_relative(
            "depot",
            dx,
            dy,
            padding=60,
            threshold=0.80
        )

        # 背包介面尚未開啟 → 點 menu
        if not depot:
            self.click(menu)
            self.input_wait()

            depot = self.find_relative(
                "depot",
                dx,
                dy,
                padding=80,
                threshold=0.80
            )

            if not depot:
                self.log_info(
                    "menu 已點擊，但仍找不到 depot"
                )
                return

        # depot 只點一次
        self.click(depot)

        # 點完立即 polling，最多 5 秒
        pages = self.wait_depot_ready(
            dx,
            dy,
            timeout=5.0
        )

        if not pages:
            self.log_info(
                "無法取得倉庫頁面 → 本次結束"
            )
            return

        stored = self.process_depot_pages(
            pages,
            dx,
            dy
        )

        if not stored:
            return

        # -----------------------------------------------------
        # 合成的唯一觸發條件：
        # 倉庫儲存完成後，Backpack_full 仍然存在
        # -----------------------------------------------------

        if force_store:
            backpack_still_full = True
            self.log_info(
                "WOG_FORCE_STORE=1：跳過存倉後 Backpack_full，強制進入合成測試"
            )
        else:
            backpack_still_full = self.find_fullscreen(
                "Backpack_full",
                threshold=0.80
            )

        if not backpack_still_full:
            return

        self.log_info(
            "觸發自動合成：倉庫後仍 Backpack_full"
        )

        self.auto_synthesis()
        self.log_info(
            "本輪倉庫／合成流程結束，等待下一次 Backpack_full 檢查"
        )
        return

    # =========================================================
    # Future
    # =========================================================

    def auto_merge(self):
        pass

    def auto_salvage(self):
        pass
