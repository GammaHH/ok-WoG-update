import time

from src.task.BaseWoGTask import BaseWoGTask
from ok.feature.Box import Box


class AutoSynthesisTask(BaseWoGTask):
    """
    獨立的自動合成 BaseTask。

    從 AutoStoreMergeSalvageTask 拆出，只保留：
    - 進入 / 確認 synthesis 頁
    - Auto Add
    - 綠 / 藍 / 空位顏色判斷
    - synthesis_start
    - 達到停止條件後退出 synthesis

    不包含：
    - Backpack_full 觸發
    - 倉庫儲存
    - TriggerTask
    - auto_merge
    - auto_salvage
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "自動合成"
        self.description = "自動進入合成介面並連續合成綠色／藍色素材；偵測到空位或其他顏色時會自動停止。"

        self.default_config = {
            "連續合成次數": 50,
        }

        self.config_description = {
            "連續合成次數":
                "設定單次任務最多連續合成幾次。僅會繼續處理綠色／藍色素材；偵測到空位或其他顏色時會立即停止，以避免誤合成。",
        }

        # 合成一般操作間隔
        self.synthesis_action_delay = 1.0

        # 合成安全設定
        self.color_tolerance = 5

        # 空位色比例門檻
        self.empty_ratio_threshold = 0.001

        self.max_synthesis_rounds = 50

    # =========================================================
    # BaseTask entry
    # =========================================================

    def run(self):
        return self.auto_synthesis()

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

    # =========================================================
    # Common / Anchor
    # =========================================================

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

    def find_menu_anchor(self):
        menu = self.find_fullscreen(
            "menu",
            threshold=0.80
        )

        if not menu:
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
    # Synthesis
    # =========================================================

    def synthesis_wait(self):
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
        只使用縮小後的 synthesis_item 區域做顏色判定。

        不再使用 synthesis_item_avoid。

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


        return result

    def find_synthesis_tab_box(self):
        """
        synthesis / synthesis_on 是同一個 tab 的 OFF / ON 外觀。
        這裡只用模板找 tab 的位置，不拿模板名稱直接判斷狀態。
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
        判斷 synthesis 頁是否真的已開啟。

        可接受的頁面證據：
        1. autoadd_synthesis 模板出現在預期位置
        2. synthesis_start 模板出現在預期位置
        3. synthesis_item 區域能辨認出 green / blue / empty 顏色

        synthesis_on / synthesis 只負責定位 tab，不單獨決定 ON/OFF。
        """

        if not synthesis_box:
            return False

        synthesis_dx, synthesis_dy = (
            self.get_anchor_offset(
                synthesis_box,
                "synthesis_on"
            )
        )

        # ---------------------------------------------------------
        # Evidence 1：Auto Add
        # ---------------------------------------------------------
        autoadd = self.find_relative(
            "autoadd_synthesis",
            synthesis_dx,
            synthesis_dy,
            padding=35,
            threshold=0.70
        )

        if autoadd:
            return True

        # ---------------------------------------------------------
        # Evidence 2：Start
        # ---------------------------------------------------------
        start = self.find_relative(
            "synthesis_start",
            synthesis_dx,
            synthesis_dy,
            padding=35,
            threshold=0.70
        )

        if start:
            return True

        # ---------------------------------------------------------
        # Evidence 3：synthesis_item 區域已有可辨認的顏色
        # synthesis_item_avoid 仍排除，不讓中央區域干擾。
        # ---------------------------------------------------------
        item_box = self.relative_box(
            "synthesis_item",
            synthesis_dx,
            synthesis_dy
        )

        item_state = self.classify_synthesis_item(
            item_box,
            avoid_box
        )

        if item_state in (
            "green",
            "blue",
            "empty"
        ):
            return True

        return False

    def synthesis_page_ready(
        self,
        synthesis_box
    ):
        """
        真正判斷目前是否已經在合成介面。

        只使用頁面控制項模板確認：
        - autoadd_synthesis
        - synthesis_start

        兩者任一模板在預期位置匹配成功，就視為 synthesis 介面 READY。
        不使用 synthesis_item 顏色來判斷是否進入介面。
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

        if start:
            return True

        return False

    def locate_synthesis_tab(self):
        """
        只負責找 synthesis tab 的位置。
        優先找 synthesis_on，找不到才找 synthesis。
        不在這裡直接斷言頁面 ON/OFF。
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

    def detect_synthesis_state(self):
        """
        回傳：
            ("ready", box)   已確定在合成介面
            ("tab", box)     只找到 synthesis tab，但頁面控制項尚未確認
            ("unknown", None)

        這樣 Task 關掉重開時，會先判斷「是否真的已到合成介面」，
        而不是看到 synthesis_on 就直接開始 Auto Add。
        """

        synthesis_box = self.locate_synthesis_tab()

        if not synthesis_box:
            return "unknown", None

        if self.synthesis_page_ready(
            synthesis_box
        ):
            return "ready", synthesis_box

        return "tab", synthesis_box

    def wait_synthesis_on(
        self,
        timeout=5.0,
        synthesis_click_box=None
    ):
        """
        確認是否真正進入合成介面。

        規則：
        1. 每次先看頁面是否 READY。
        2. READY → 絕不再點 synthesis。
        3. 尚未 READY 且提供可點 tab → 點一次，等 1 秒，再重新判斷。
        4. 最多約 5 秒。

        關鍵是判斷「頁面 READY」，不是只判 synthesis_on 模板。
        """

        end_time = time.time() + timeout
        attempt = 0

        while time.time() < end_time:
            attempt += 1

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
                self.sleep(
                    0.25
                )

        return None

    def wait_synthesis_off(
        self,
        timeout=5.0
    ):
        """
        退出成功的判準：合成頁控制項不再 READY。
        """

        end_time = time.time() + timeout

        while time.time() < end_time:
            state, _box = (
                self.detect_synthesis_state()
            )

            if state != "ready":
                return True

            self.sleep(
                0.25
            )

        return False

    def exit_synthesis(self):
        state, synthesis_box = (
            self.detect_synthesis_state()
        )

        if state != "ready":
            return True

        if not synthesis_box:
            return False

        self.click(
            synthesis_box
        )

        self.synthesis_wait()

        if self.wait_synthesis_off(
            timeout=5.0
        ):
            return True

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

                # 不再額外固定等待 3 秒，
                # 僅沿用一般 synthesis 操作等待。
                self.synthesis_wait()

            state = self.classify_synthesis_item(
                item_box
            )


            # 空位色達門檻 → 終止
            if state == "empty":
                self.exit_synthesis()
                return True

            # 其他顏色 / unsafe → 終止
            if state not in (
                "green",
                "blue"
            ):
                self.exit_synthesis()
                return False

            self.click(
                start_box
            )
            self.synthesis_wait()

        self.exit_synthesis()
        return False

    def auto_synthesis(self):
        """
        一般 BaseTask 入口。

        Task 每次啟動 / 關掉重開都先重新確認：
        1. 是否真的已經在 synthesis 介面（頁面控制項 READY）
        2. 若已在 → 直接開始，不再點 tab
        3. 若不在 → 找 menu / synthesis tab，再進入並等待 READY
        """

        # -----------------------------------------------------
        # 先確認「真的已在合成介面」
        # -----------------------------------------------------
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

            # 先找 OFF 外觀的 synthesis tab。
            synthesis = self.find_relative(
                "synthesis",
                menu_dx,
                menu_dy,
                padding=40,
                threshold=0.70
            )

            # 看不到 tab → 先點 menu 展開。
            if not synthesis:
                self.click(
                    menu
                )
                self.synthesis_wait()

                # menu 展開後，先再確認一次頁面是否已 READY。
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
                    # OFF 模板沒找到時，退而使用 tab 定位器，
                    # 但仍必須等待頁面控制項 READY 才算成功。
                    synthesis = self.locate_synthesis_tab()

                if not synthesis:
                    return False

                synthesis_on = (
                    self.wait_synthesis_on(
                        timeout=5.0,
                        synthesis_click_box=synthesis
                    )
                )

                if not synthesis_on:
                    return False

        # -----------------------------------------------------
        # 到這裡一定是「頁面 READY」，才允許 Auto Add
        # -----------------------------------------------------
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

