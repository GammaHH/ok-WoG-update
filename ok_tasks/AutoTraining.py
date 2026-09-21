import re
import time

from ok import TriggerTask
from src.task.BaseWoGTask import BaseWoGTask
from ok.feature.Box import Box


class AutoTraining(BaseWoGTask, TriggerTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "自動訓練"
        self.description = "依照你勾選的優先順序自動強化訓練項目，並持續偵測目前金錢；買不起優先項目時會等待，金錢達上限時可選擇強化其他可負擔項目。"

        # =====================================================
        # 使用者 UI 配置
        # =====================================================

        # 程式內部的 canonical 順序。
        self.train_priority_options = [
            "力量",
            "堅韌",
            "生命力",
            "迅捷",
            "疾驰",
            "背包擴充",
            "精準",
            "致命一擊",
            "專注",
            "敏捷",
            "擴充金庫",
            "討伐",
            "遠征防禦",
            "巨人獵手",
            "增幅",
            "庇護",
            "決鬥",
            "戰鬥防禦",
            "暴擊防禦",
            "絕緣",
            "耐熱",
            "解毒",
            "鋼鐵之膚",
            "不屈",
            "耐雷",
            "耐火",
            "免疫",
            "冷卻加速",
            "穿透",
            "感電防禦",
            "灼燒防禦",
            "中毒防禦",
            "再生",
            "倉庫擴充",
            "狩獵時間縮短",
            "装備回收",
            "飾品回收",
            "翅膀回收",
            "符文回收",
            "寵物召唤券回",
        ]

        # 40 個 checkbox 拆成 7 個 UI row，避免文字被壓縮。
        self.train_priority_groups = {
            "優先強化項目 1": [
                "力量",
                "堅韌",
                "生命力",
                "迅捷",
                "疾驰",
                "背包擴充",
            ],
            "優先強化項目 2": [
                "精準",
                "致命一擊",
                "專注",
                "敏捷",
                "擴充金庫",
                "討伐",
            ],
            "優先強化項目 3": [
                "遠征防禦",
                "巨人獵手",
                "增幅",
                "庇護",
                "決鬥",
                "戰鬥防禦",
            ],
            "優先強化項目 4": [
                "暴擊防禦",
                "絕緣",
                "耐熱",
                "解毒",
                "鋼鐵之膚",
                "不屈",
            ],
            "優先強化項目 5": [
                "耐雷",
                "耐火",
                "免疫",
                "冷卻加速",
                "穿透",
                "感電防禦",
            ],
            "優先強化項目 6": [
                "灼燒防禦",
                "中毒防禦",
                "再生",
                "倉庫擴充",
                "狩獵時間縮短",
                "装備回收",
            ],
            "優先強化項目 7": [
                "飾品回收",
                "翅膀回收",
                "符文回收",
                "寵物召唤券回收",
            ],
        }

        self.default_config = {
            "_enabled": True,
            "金錢偵測間隔": 10.0,
            "優先強化項目 1": [],
            "優先強化項目 2": [],
            "優先強化項目 3": [],
            "優先強化項目 4": [],
            "優先強化項目 5": [],
            "優先強化項目 6": [],
            "優先強化項目 7": [],
            "滿錢時強化未勾選": True,
        }

        # 初始值；實際值會由 UI「金錢偵測間隔」動態覆蓋。
        self.trigger_interval = 10.0

        self.config_description = {
            "金錢偵測間隔":
                "設定自動訓練等待期間多久重新偵測一次目前金錢，單位為秒。數值越小反應越快，但會增加 OCR 偵測頻率。",
            "優先強化項目 1":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "優先強化項目 2":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "優先強化項目 3":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "優先強化項目 4":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "優先強化項目 5":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "優先強化項目 6":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "優先強化項目 7":
                "勾選此列中想優先強化的項目。程式會依內建順序優先處理已勾選項目；若目前金錢不足，會等待下一次金錢偵測。",
            "滿錢時強化未勾選":
                "開啟後，只有在金錢達到上限時，才會從未勾選的訓練項目中選擇目前可負擔者進行強化，以避免資源溢出。",
        }

        self.config_type = {
            key: {
                "type": "multi_selection",
                "options": options,
            }
            for key, options in self.train_priority_groups.items()
        }

        # 點選訓練項目後，等右側資料更新
        self.select_wait = 0.2

        # 每次滾動後等待 UI 穩定
        self.scroll_wait = 0.5

        # train_type 使用拖曳滾動。
        # 遊戲的位移比例約為 1:1，因此不再使用固定百分比。
        #
        # 畫面一次可見 2 列卡片：
        # card_height = train_type.height / 2
        #
        # 每次要往下移 2 張卡：
        # swipe_distance = card_height * 2
        #                = train_type.height
        # 舊版實機可用的滑鼠滾輪方式
        self.scroll_count = -19


        # 每次真正送 scroll 前，先強制把遊戲視窗拉到前景。
        self.focus_before_scroll_wait = 0.25

        # 連續幾次滾動都沒有新 category，就視為到底
        self.no_new_limit = 1

        # 防止異常無限捲動
        self.max_scroll_rounds = 10

        # OCR threshold
        self.ocr_threshold = 0.10

        # train tab 狀態色（使用者實測）
        # ON  = RGB (242, 202, 56)
        # OFF = RGB (237, 226, 198)
        self.train_on_rgb = (242, 202, 56)
        self.train_off_rgb = (237, 226, 198)
        self.train_state_tolerance = 2

        # train_money「金額不足」文字色（使用者實測）
        # 紅字本身不能直接代表沒錢，因為 prerequisite 文字也會是紅色。
        # 只有「cost OCR 可解析成數字」+「train_money 內存在此紅色」才判定沒錢。
        self.train_insufficient_rgb = (208, 69, 53)
        self.train_insufficient_tolerance = 5

        # ON/OFF 色只要有抓到就可判斷。
        # train tab 的狀態色只佔框內小區域，不使用百分比門檻。
        self.train_state_min_ratio = 0.0

        # 進入 / 切換主要 UI 後固定等待 2 秒
        # 避免 train_on 剛出現但內容、money、train_type 還沒完成渲染
        self.ui_enter_wait = 2.0

        # BUY loop runtime 設定（run 時由 UI config 覆蓋）
        self.money_poll_interval = 1.0
        self.cap_fallback_enabled = True

        # PAY 後等 UI 更新；這是實作 timing，不放 UI 避免設定過度複雜。
        self.purchase_wait = 2.0

        # 記憶目前金額 / 上限
        self.current_money = None
        self.money_cap = None
        self.last_money_raw = ""

        # mapping 每次 Task run 只建立一次。
        # NAV 重新進入 train 時不重新掃描。
        self.train_scan_completed = False

        # 目前訓練列表所在的 scroll round。
        # 0 = 最上方。
        # BUY 時盡量留在 train 頁，不再每次 OFF→ON。
        self.current_train_scroll_round = 0

        # 只針對「cost=None 且不是已知 prerequisite」的異常 OCR
        # 每種 raw 最多回報一次，避免 LOG 洗版。
        self.reported_unknown_train_money = set()


        # train_type 鎖定卡片判斷：
        # 黑卡背景會大面積落在 RGB 0~70。
        self.locked_dark_range = {
            "r": (0, 70),
            "g": (0, 70),
            "b": (0, 70),
        }

        # 單一卡片有 35% 以上為深色，就視為黑色鎖定卡。
        self.locked_slot_dark_ratio = 0.35

        # 同一畫面 6 格中有至少 3 格是黑卡，
        # 掃完這一頁仍可用的項目後就停止，不再繼續下滑。
        self.locked_slots_stop_count = 3

        # 掃描結果
        self.train_table = {}
        self.discovery_order = []

    def should_trigger(self):
        """
        TriggerTask 的觸發間隔直接綁定 UI：
        「金錢偵測間隔」。

        這樣不是在 run() 裡 while True；
        而是由 ok-script TaskExecutor 定期觸發一次 run()。
        """

        config = getattr(
            self,
            "config",
            {}
        )

        try:
            interval = float(
                config.get(
                    "金錢偵測間隔",
                    10.0
                )
            )
        except (
            TypeError,
            ValueError
        ):
            interval = 10.0

        self.trigger_interval = max(
            0.2,
            interval
        )

        return super().should_trigger()

    # =========================================================
    # Common
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
        return self.find_fullscreen(
            "menu",
            threshold=0.80
        )

    def get_anchor_offset(
        self,
        anchor,
        reference_name
    ):
        reference = self.get_box_by_name(
            reference_name
        )

        return (
            anchor.x - reference.x,
            anchor.y - reference.y
        )

    def relative_box(
        self,
        name,
        dx,
        dy,
        padding=0
    ):
        ref = self.get_box_by_name(
            name
        )

        return Box(
            max(
                0,
                ref.x + dx - padding
            ),
            max(
                0,
                ref.y + dy - padding
            ),
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
    # Train tab state
    # =========================================================

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

    def find_train_tab_box(self):
        """
        train / train_on 是同一個 tab 的 OFF / ON 外觀。
        模板只拿來定位，不直接代表狀態。
        """

        box = self.find_fullscreen(
            "train_on",
            threshold=0.65
        )

        if box:
            return box

        return self.find_fullscreen(
            "train",
            threshold=0.65
        )

    def train_page_controls_visible(
        self,
        train_box
    ):
        """
        用 Train 頁右側的「類別名稱」確認是否真的已進 Train。

        template 只負責定位 tab。
        只要 train_category OCR 有非空文字，就視為 Train ON。

        不能要求 category 已存在於 priority list / mapping，
        否則第一次遇到新項目（例如「再生」）時會把真正的
        Train ON 誤判成 OFF，接著再點一次 tab 反而把 Train 關掉。
        """

        if not train_box:
            return False

        train_dx, train_dy = (
            self.get_anchor_offset(
                train_box,
                "train_on"
            )
        )

        category_box = self.relative_box(
            "train_category",
            train_dx,
            train_dy
        )

        raw = self.ocr_text(
            category_box
        )

        if not raw:
            return False

        category = self.normalize_category(
            raw.strip()
        )

        return bool(
            category
        )

    def detect_train_state(self):
        """
        回傳：
            ("on", box)
            ("off", box)
            ("unknown", box/None)

        ON 優先用 Train 頁內容確認；
        OFF 才用 tab 的 OFF 色作輔助。

        避免「其實已 ON，但 RGB 沒命中」
        造成程式再點一次把 Train 關掉。
        """

        box = self.find_train_tab_box()

        if not box:
            return "unknown", None

        if self.train_page_controls_visible(
            box
        ):
            return "on", box

        off_range = self.make_color_range(
            self.train_off_rgb,
            max(
                self.train_state_tolerance,
                6
            )
        )

        off_ratio = self.calculate_color_percentage(
            off_range,
            box
        )

        if off_ratio > 0:
            return "off", box

        return "unknown", box

    def detect_numeric_cost_insufficient(
        self,
        cost_box,
        cost
    ):
        """
        判斷 train_money 是否為「數字金額 + 紅字」。

        prerequisite 文字同樣可能是紅色，因此顏色不能單獨判斷。
        只有 cost 已成功解析成數字時，RGB (208, 69, 53) ±5
        才代表目前金錢不足。

        回傳：
            (is_insufficient, red_ratio)
        """

        if cost is None:
            return False, 0.0

        red_range = self.make_color_range(
            self.train_insufficient_rgb,
            self.train_insufficient_tolerance
        )

        red_ratio = self.calculate_color_percentage(
            red_range,
            cost_box
        )

        return red_ratio > 0, red_ratio

    # =========================================================
    # OCR helpers
    # =========================================================

    @staticmethod
    def _ocr_piece_text(item):
        """
        ok-script OCR 正常會回傳 Box list，文字位於 Box.name。
        這裡也容忍 string / tuple，方便 DEBUG。
        """
        if item is None:
            return ""

        if isinstance(item, str):
            return item

        name = getattr(
            item,
            "name",
            None
        )

        if name is not None:
            return str(name)

        if isinstance(
            item,
            (tuple, list)
        ):
            if len(item) > 0:
                return str(item[0])

        return str(item)

    def ocr_text(
        self,
        box
    ):
        """
        讀取指定框 OCR，依畫面位置排序後合併文字。
        不使用 ok-script 自帶 OCR log，改由本 Task 輸出乾淨 LOG。
        """
        result = self.ocr(
            box=box,
            threshold=self.ocr_threshold,
            log=False
        )

        if not result:
            return ""

        if isinstance(result, str):
            return result.strip()

        try:
            ordered = sorted(
                result,
                key=lambda item: (
                    getattr(item, "y", 0),
                    getattr(item, "x", 0)
                )
            )
        except TypeError:
            ordered = result

        parts = []

        for item in ordered:
            text = self._ocr_piece_text(
                item
            ).strip()

            if text:
                parts.append(text)

        return "".join(parts).strip()

    @staticmethod
    def parse_compact_number(
        text
    ):
        """
        支援：
            34384
            1,050,000
            231.000      # OCR 把千分位逗號看成點
            1.911.000
            355.5K
            220M
            1.2B

        規則：
        - 無 K/M/B/T suffix 時，若符合 1~3 位 + 每三位分組，
          ',' 或 '.' 都視為千分位。
        - 有 suffix 時，小數點保留為 decimal。
        """

        if not text:
            return None

        cleaned = (
            str(text)
            .upper()
            .replace(" ", "")
            .replace("Ｏ", "0")
        )

        match = re.search(
            r"(\d[\d,.]*)([KMBT]?)",
            cleaned
        )

        if not match:
            return None

        number_token = match.group(1)
        suffix = match.group(2)

        if not suffix:
            # 231.000 / 1.911.000 / 1,050,000
            # 全部視為整數千分位。
            if re.fullmatch(
                r"\d{1,3}(?:[.,]\d{3})+",
                number_token
            ):
                digits = re.sub(
                    r"[.,]",
                    "",
                    number_token
                )

                return int(
                    digits
                )

        # 有 K/M/B/T 時保留 '.' 當小數點；
        # ',' 一律只當千分位。
        normalized = number_token.replace(
            ",",
            ""
        )

        # 沒 suffix 卻有多個 dot，保守視為千分位。
        if (
            not suffix
            and normalized.count(".") > 1
        ):
            normalized = normalized.replace(
                ".",
                ""
            )

        try:
            value = float(
                normalized
            )
        except ValueError:
            return None

        multiplier = {
            "": 1,
            "K": 1_000,
            "M": 1_000_000,
            "B": 1_000_000_000,
            "T": 1_000_000_000_000,
        }.get(
            suffix,
            1
        )

        return int(
            round(
                value * multiplier
            )
        )

    def parse_money_pair(
        self,
        text
    ):
        """
        例如：
        355.5K/220M
        34384/220M
        """
        if not text:
            return None, None

        cleaned = (
            str(text)
            .upper()
            .replace(" ", "")
            .replace(",", "")
        )

        # 常見 slash OCR 變體
        cleaned = cleaned.replace(
            "／",
            "/"
        )

        parts = cleaned.split(
            "/",
            1
        )

        if len(parts) != 2:
            return None, None

        current = (
            self.parse_compact_number(
                parts[0]
            )
        )

        cap = (
            self.parse_compact_number(
                parts[1]
            )
        )

        return current, cap

    @staticmethod
    def parse_level(
        text
    ):
        """
        train_LV 應只框「目前等級」那一格。

        遊戲在目前 Lv.0 時，該格不顯示文字；
        因此 OCR 完全沒讀到內容時，直接視為 Lv.0。

        若 OCR 有文字但無法解析成等級，
        仍回傳 None，避免把真正的 OCR 異常誤當 Lv.0。
        """

        raw = (
            ""
            if text is None
            else str(text).strip()
        )

        if not raw:
            return 0

        match = re.search(
            r"(?i)L\s*V\s*\.?\s*(\d+)",
            raw
        )

        if match:
            return int(
                match.group(1)
            )

        # fallback：框內理論上只有目前 LV
        match = re.search(
            r"(\d+)",
            raw
        )

        if match:
            return int(
                match.group(1)
            )

        return None


    @staticmethod
    def parse_train_requirement(
        text
    ):
        """
        解析 train_money 區域的前置條件文字。

        支援常見格式，例如：
            達到巨人獵手 LV.5
            达到巨人猎手LV.5
            需要巨人獵手 LV.5
            需達到巨人獵手 LV.5
            巨人獵手 LV.5

        回傳：
            (category, required_level)

        正常金額 / 無法辨識：
            (None, None)
        """

        if not text:
            return None, None

        raw = (
            str(text)
            .strip()
            .replace("Ｌ", "L")
            .replace("Ｖ", "V")
        )

        # 正常金額不應被誤判成 prerequisite。
        compact = (
            raw.upper()
            .replace(",", "")
            .replace(" ", "")
        )

        if re.fullmatch(
            r"\d+(?:\.\d+)?[KMBT]?",
            compact
        ):
            return None, None

        # 先吃掉常見前綴，再抓「項目名稱 + LV.N」。
        match = re.search(
            r"(?:需達到|需达到|達到|达到|需要|需求|要求)?\s*"
            r"(.+?)\s*L\s*V\s*\.?\s*(\d+)",
            raw,
            re.IGNORECASE
        )

        if not match:
            return None, None

        category = match.group(1).strip(
            " ：:，,。."
        )

        if not category:
            return None, None

        required_level = int(
            match.group(2)
        )

        return category, required_level

    # =========================================================
    # Enter Train
    # =========================================================

    def wait_train_on(
        self,
        timeout=5.0
    ):
        end_time = (
            time.time()
            + timeout
        )

        while (
            time.time()
            < end_time
        ):
            state, train_box = (
                self.detect_train_state()
            )

            if state == "on":
                return train_box

            self.sleep(
                0.25
            )

        return None

    def enter_train(self):
        """
        安全 NAV：

        1. 已確認 Train ON → 直接使用。
        2. tab 已可見但目前不是 ON → 只點一次，再確認頁面。
        3. tab 完全不可見 → menu 只開一次，再點 Train 一次。

        關鍵：
        「點 Train 後確認失敗」不會立刻再點第二次，
        避免 ON → OFF → menu 的來回循環。
        """

        state, train_box = (
            self.detect_train_state()
        )

        if (
            state == "on"
            and train_box
        ):
            return train_box

        # tab 已經在畫面上：只嘗試一次。
        if train_box:
            self.click(
                train_box
            )

            self.sleep(
                self.ui_enter_wait
            )

            return self.wait_train_on(
                timeout=5.0
            )

        # tab 完全不可見才碰 menu。
        menu = self.find_menu_anchor()

        if not menu:
            return None

        self.click(
            menu
        )

        self.sleep(
            self.ui_enter_wait
        )

        state, train_box = (
            self.detect_train_state()
        )

        if (
            state == "on"
            and train_box
        ):
            return train_box

        if not train_box:
            train_box = self.find_train_tab_box()

        if not train_box:
            return None

        self.click(
            train_box
        )

        self.sleep(
            self.ui_enter_wait
        )

        return self.wait_train_on(
            timeout=5.0
        )

    # =========================================================
    # Money OCR
    # =========================================================

    def _read_global_money_once(self):
        """
        單次 money OCR。

        回傳：
            current, cap, raw

        這個 helper 本身不做任何 UI 導航，
        讓 read_global_money() 可以安全地做 retry / menu recovery。
        """

        menu = self.find_menu_anchor()

        if not menu:
            return None, None, ""

        menu_dx, menu_dy = (
            self.get_anchor_offset(
                menu,
                "menu"
            )
        )

        money_box = self.relative_box(
            "money",
            menu_dx,
            menu_dy
        )

        result = self.ocr(
            box=money_box,
            threshold=self.ocr_threshold,
            log=False
        )

        raw = ""

        if isinstance(
            result,
            str
        ):
            raw = result.strip()

        elif result:
            pieces = []

            for item in result:
                piece = self._ocr_piece_text(
                    item
                ).strip()

                if piece:
                    pieces.append(
                        piece
                    )

            slash_pieces = [
                piece
                for piece in pieces
                if (
                    "/" in piece
                    or "／" in piece
                )
            ]

            if slash_pieces:
                # 例如 OCR = [5, 93779/340M]
                # 只取真正包含 current/cap 的那一段。
                raw = max(
                    slash_pieces,
                    key=len
                )
            else:
                raw = "".join(
                    pieces
                ).strip()

        current, cap = (
            self.parse_money_pair(
                raw
            )
        )

        self.last_money_raw = raw

        if current is not None:
            self.current_money = current

        if cap is not None:
            self.money_cap = cap

        return current, cap, raw

    def read_global_money(self):
        """
        Money OCR recovery：

        1. 目前畫面先重試 2 次。
        2. 如果仍完全掃不到，只要 menu anchor 找得到：
           → 點 menu 讓主 UI 展開
           → 等 UI 完成渲染
           → 再重試 money OCR。
        3. 若仍失敗才回傳 None。

        這樣不會因為一次 WGC / UI 渲染空幀，
        就整個 Trigger 直接放棄。
        """

        # 先在目前畫面 retry。
        for attempt in range(2):
            current, cap, raw = (
                self._read_global_money_once()
            )

            if (
                current is not None
                and cap is not None
            ):
                return current, cap, raw

            if attempt == 0:
                self.sleep(
                    0.35
                )

        # money 連續讀不到：
        # 只要 menu anchor 還存在，就先點 menu 讓主 UI 重新展開，
        # 不再要求當下必須被判定為 Train ON。
        menu = self.find_menu_anchor()

        if menu:
            self.log_info(
                "Money OCR 連續失敗：找到 menu，開 menu 重新辨識"
            )

            self.click(
                menu
            )

            # UI 被切換後，舊的 Train scroll round 不再可信。
            self.current_train_scroll_round = 0

            self.sleep(
                self.ui_enter_wait
            )

            for attempt in range(3):
                current, cap, raw = (
                    self._read_global_money_once()
                )

                if (
                    current is not None
                    and cap is not None
                ):
                    return current, cap, raw

                if attempt < 2:
                    self.sleep(
                        0.35
                    )

        # 最後仍失敗：保持安全，不做 BUY。
        return None, None, self.last_money_raw

    def read_train_detail(
        self,
        category_box,
        level_box,
        cost_box
    ):
        category_raw = self.ocr_text(
            category_box
        )

        level_raw = self.ocr_text(
            level_box
        )

        cost_raw = self.ocr_text(
            cost_box
        )

        level = self.parse_level(
            level_raw
        )

        requirement_category, requirement_level = (
            self.parse_train_requirement(
                cost_raw
            )
        )

        if requirement_category:
            requirement_category = (
                self.normalize_category(
                    requirement_category
                )
            )
            cost = None
            insufficient_money = False
            insufficient_red_ratio = 0.0
        else:
            cost = (
                self.parse_compact_number(
                    cost_raw
                )
            )

            (
                insufficient_money,
                insufficient_red_ratio
            ) = self.detect_numeric_cost_insufficient(
                cost_box,
                cost
            )

        return {
            "category": self.normalize_category(
                category_raw.strip()
            ),
            "level": level,
            "level_raw": level_raw,
            "cost": cost,
            "cost_raw": cost_raw,
            "requirement_category": requirement_category,
            "requirement_level": requirement_level,
            "insufficient_money": insufficient_money,
            "insufficient_red_ratio": insufficient_red_ratio,
        }

    # =========================================================
    # Auto BUY helpers
    # =========================================================

    @staticmethod
    def normalize_category(
        category
    ):
        """
        將少數 OCR 繁簡差異統一成 UI options 使用的名稱。
        """

        text = str(
            category or ""
        ).strip()

        aliases = {
            "疾馳": "疾驰",
            "致命一": "致命一擊",
            "致命擊": "致命一擊",
            "裝備回收": "装備回收",
            "寵物召喚券回": "寵物召唤券回",
            "寵物召喚券回收": "寵物召唤券回",
            "寵物召唤券回收": "寵物召唤券回",
        }

        return aliases.get(
            text,
            text
        )

    def apply_user_config(self):
        """
        Task UI 的設定在 run 時讀取。
        """

        config = getattr(
            self,
            "config",
            {}
        )

        try:
            interval = float(
                config.get(
                    "金錢偵測間隔",
                    10.0
                )
            )
        except (
            TypeError,
            ValueError
        ):
            interval = 10.0

        self.money_poll_interval = max(
            0.2,
            interval
        )

        self.cap_fallback_enabled = bool(
            config.get(
                "滿錢時強化未勾選",
                True
            )
        )

        selected = []

        # 六個 UI row 合併成一份 priority selection。
        for key in self.train_priority_groups:
            values = config.get(
                key,
                []
            )

            if isinstance(
                values,
                list
            ):
                selected.extend(
                    values
                )

        # 相容舊版單一「優先強化項目」設定；
        # 如果 config 裡還留著舊值，仍會讀進來。
        legacy_values = config.get(
            "優先強化項目",
            []
        )

        if isinstance(
            legacy_values,
            list
        ):
            selected.extend(
                legacy_values
            )

        selected_set = {
            self.normalize_category(
                value
            )
            for value in selected
        }

        # 實際 BUY 優先順序固定依目前 31 項 canonical 順序。
        self.priority_categories = [
            category
            for category in self.train_priority_options
            if category in selected_set
        ]

    # =========================================================
    # Scan Train Types
    # =========================================================

    @staticmethod
    def train_slot_points(
        train_type_box
    ):
        """
        畫面可見區為 3 欄 × 2 列。
        不需要每個 type 各自做 template。

        捲動後仍然點擊這 6 個可見位置。
        """
        points = []

        for row in range(2):
            for col in range(3):

                x = int(
                    train_type_box.x
                    + train_type_box.width
                    * (
                        col + 0.5
                    )
                    / 3
                )

                y = int(
                    train_type_box.y
                    + train_type_box.height
                    * (
                        row + 0.5
                    )
                    / 2
                )

                points.append(
                    (
                        x,
                        y
                    )
                )

        return points

    def remember_train_item(
        self,
        detail,
        scroll_round,
        slot_index
    ):
        category = self.normalize_category(
            detail.get(
                "category",
                ""
            )
        )

        level = detail.get(
            "level"
        )

        cost = detail.get(
            "cost"
        )

        if not category:
            return False

        if (
            level is None
            and cost is None
        ):
            return False

        is_new = (
            category
            not in self.train_table
        )

        # 第一次發現的位置最重要；
        # 重疊掃描只更新 LV / cost，不覆蓋定位。
        if is_new:
            self.train_table[
                category
            ] = {
                "level": level,
                "cost": cost,
                "level_raw": detail.get(
                    "level_raw",
                    ""
                ),
                "cost_raw": detail.get(
                    "cost_raw",
                    ""
                ),
                "requirement_category": detail.get(
                    "requirement_category"
                ),
                "requirement_level": detail.get(
                    "requirement_level"
                ),
                "scroll_round": scroll_round,
                "slot_index": slot_index,
            }

            self.discovery_order.append(
                category
            )
        else:
            self.train_table[
                category
            ].update(
                {
                    "level": level,
                    "cost": cost,
                    "level_raw": detail.get(
                        "level_raw",
                        ""
                    ),
                    "cost_raw": detail.get(
                        "cost_raw",
                        ""
                    ),
                    "requirement_category": detail.get(
                        "requirement_category"
                    ),
                    "requirement_level": detail.get(
                        "requirement_level"
                    ),
                }
            )

        return is_new

    @staticmethod
    def train_slot_boxes(
        train_type_box
    ):
        """
        將 train_type 可見區切成 3 欄 × 2 列。
        """
        boxes = []

        for row in range(2):
            for col in range(3):

                left = int(
                    train_type_box.x
                    + train_type_box.width
                    * col
                    / 3
                )

                right = int(
                    train_type_box.x
                    + train_type_box.width
                    * (col + 1)
                    / 3
                )

                top = int(
                    train_type_box.y
                    + train_type_box.height
                    * row
                    / 2
                )

                bottom = int(
                    train_type_box.y
                    + train_type_box.height
                    * (row + 1)
                    / 2
                )

                boxes.append(
                    Box(
                        left,
                        top,
                        max(1, right - left),
                        max(1, bottom - top)
                    )
                )

        return boxes

    def is_locked_train_slot(
        self,
        slot_box
    ):
        dark_ratio = (
            self.calculate_color_percentage(
                self.locked_dark_range,
                slot_box
            )
        )

        return (
            dark_ratio
            >= self.locked_slot_dark_ratio
        ), dark_ratio

    def scan_visible_train_types(
        self,
        train_type_box,
        category_box,
        level_box,
        cost_box,
        scroll_round
    ):
        new_count = 0

        slot_boxes = self.train_slot_boxes(
            train_type_box
        )

        locked_flags = []

        for slot_box in slot_boxes:
            locked, _ratio = (
                self.is_locked_train_slot(
                    slot_box
                )
            )

            locked_flags.append(
                locked
            )

        locked_count = sum(
            1
            for locked in locked_flags
            if locked
        )

        stop_after_page = (
            locked_count
            >= self.locked_slots_stop_count
        )

        points = self.train_slot_points(
            train_type_box
        )

        for slot_index, (
            x,
            y
        ) in enumerate(
            points
        ):
            if locked_flags[
                slot_index
            ]:
                continue

            self.click(
                x,
                y
            )

            self.sleep(
                self.select_wait
            )

            detail = self.read_train_detail(
                category_box,
                level_box,
                cost_box
            )

            if self.remember_train_item(
                detail,
                scroll_round,
                slot_index
            ):
                new_count += 1

        return new_count, stop_after_page

    def force_game_focus(self):
        interaction = self.executor.interaction

        hwnd_window = getattr(
            interaction,
            "hwnd_window",
            None
        )

        if hwnd_window is not None:
            try:
                hwnd_window.bring_to_front()
            except Exception:
                pass

        self.sleep(
            self.focus_before_scroll_wait
        )

    def scroll_train_type(
        self,
        train_type_box,
        scroll_round=None
    ):
        """
        舊版實機可用的 wheel scroll。
        每次 scroll 前只多做 force focus。
        """

        x = int(
            train_type_box.x
            + train_type_box.width * 0.5
        )

        y = int(
            train_type_box.y
            + train_type_box.height * 0.5
        )

        self.force_game_focus()

        self.scroll(
            x,
            y,
            self.scroll_count
        )

        self.sleep(
            self.scroll_wait
        )

    def reset_train_view(self):
        """
        回頂：

        - 已在 Train ON：
          直接點同一個 Train tab 兩次（ON → OFF → ON）。
        - 尚未在 Train：
          enter_train() 只進一次；新開 Train 本身就是頂端。

        正常流程完全不經 menu。
        """

        state, train_box = (
            self.detect_train_state()
        )

        if (
            state == "on"
            and train_box
        ):
            # ON -> OFF
            self.click(
                train_box
            )

            self.sleep(
                self.ui_enter_wait
            )

            # OFF -> ON
            self.click(
                train_box
            )

            self.sleep(
                self.ui_enter_wait
            )

            train_on = self.wait_train_on(
                timeout=5.0
            )

            if train_on:
                self.current_train_scroll_round = 0

            return train_on

        # 沒在 Train 時，只進入一次即可；進頁即為頂端。
        train_on = self.enter_train()

        if train_on:
            self.current_train_scroll_round = 0

        return train_on

    def scan_all_train_types(self):
        """
        每個 Task run 只建立一次 mapping。

        掃描前不再向上 scroll；
        改用 Train OFF → ON 強制回到原位。
        """

        if self.train_scan_completed:
            return True

        self.log_info(
            "CREATE MAP：開始建立訓練對應表"
        )

        train_on = self.reset_train_view()

        if not train_on:
            return False

        train_dx, train_dy = (
            self.get_anchor_offset(
                train_on,
                "train_on"
            )
        )

        train_type_box = self.relative_box(
            "train_type",
            train_dx,
            train_dy
        )

        category_box = self.relative_box(
            "train_category",
            train_dx,
            train_dy
        )

        level_box = self.relative_box(
            "train_LV",
            train_dx,
            train_dy
        )

        cost_box = self.relative_box(
            "train_money",
            train_dx,
            train_dy
        )

        # PAY / type_confirm 在正式 BUY 安全確認使用。
        self.relative_box(
            "train_type_confirm",
            train_dx,
            train_dy
        )

        self.relative_box(
            "train_pay",
            train_dx,
            train_dy
        )

        self.train_table.clear()
        self.discovery_order.clear()

        no_new_rounds = 0

        new_count, stop_after_page = (
            self.scan_visible_train_types(
                train_type_box,
                category_box,
                level_box,
                cost_box,
                0
            )
        )

        if stop_after_page:
            self.train_scan_completed = True
            self.log_train_table()
            return True

        if new_count == 0:
            no_new_rounds += 1

        for scroll_round in range(
            1,
            self.max_scroll_rounds + 1
        ):
            if (
                no_new_rounds
                >= self.no_new_limit
            ):
                break

            self.scroll_train_type(
                train_type_box,
                scroll_round
            )
            self.current_train_scroll_round = scroll_round

            new_count, stop_after_page = (
                self.scan_visible_train_types(
                    train_type_box,
                    category_box,
                    level_box,
                    cost_box,
                    scroll_round
                )
            )

            if stop_after_page:
                break

            if new_count == 0:
                no_new_rounds += 1
            else:
                no_new_rounds = 0

        self.train_scan_completed = True
        self.log_train_table()

        # 掃描結束只在這裡重置一次到頂端。
        # 後續 BUY 不會每輪關閉 / 重開 train。
        self.reset_train_view()

        return True

    # =========================================================
    # Auto BUY
    # =========================================================

    def get_train_runtime_boxes(
        self,
        train_on
    ):
        train_dx, train_dy = (
            self.get_anchor_offset(
                train_on,
                "train_on"
            )
        )

        return {
            "type": self.relative_box(
                "train_type",
                train_dx,
                train_dy
            ),
            "category": self.relative_box(
                "train_category",
                train_dx,
                train_dy
            ),
            "level": self.relative_box(
                "train_LV",
                train_dx,
                train_dy
            ),
            "cost": self.relative_box(
                "train_money",
                train_dx,
                train_dy
            ),
            "confirm": self.relative_box(
                "train_type_confirm",
                train_dx,
                train_dy
            ),
            "pay": self.relative_box(
                "train_pay",
                train_dx,
                train_dy
            ),
        }

    def locate_train_item(
        self,
        category
    ):
        """
        用 mapping 定位目標，但保持 Train 頁常駐。

        正常情況：
        - 目標在目前位置以下：只補 scroll 差值。
        - 目標在目前位置以上：OFF→ON 回頂，再往下。
        - 同 round：直接點。

        額外 recovery：
        如果使用者手動捲動 Train，
        self.current_train_scroll_round 不會同步。
        此時點 mapping slot 後若實際 category != 預期 category，
        會把它視為「滾動位置失同步」：

            category mismatch
            → Train ON→OFF→ON 回頂
            → current_train_scroll_round = 0
            → 依 mapping 重新捲到 target_round
            → 再定位一次

        最多 recovery 1 次，避免無限循環。
        """

        category = self.normalize_category(
            category
        )

        data = self.train_table.get(
            category
        )

        if not data:
            return None, None

        target_round = int(
            data.get(
                "scroll_round",
                0
            )
        )

        for attempt in range(2):

            # 先確保目前仍在 Train。
            state, train_on = (
                self.detect_train_state()
            )

            if state != "on" or not train_on:
                train_on = self.enter_train()

                if not train_on:
                    return None, None

                # 一般重新進入 Train 會回頂。
                self.current_train_scroll_round = 0

            boxes = self.get_train_runtime_boxes(
                train_on
            )

            # 目標在目前邏輯位置上方，先 reset 回頂。
            if (
                target_round
                < self.current_train_scroll_round
            ):
                train_on = self.reset_train_view()

                if not train_on:
                    return None, None

                self.current_train_scroll_round = 0

                boxes = self.get_train_runtime_boxes(
                    train_on
                )

            # 只補需要的下滑距離。
            while (
                self.current_train_scroll_round
                < target_round
            ):
                next_round = (
                    self.current_train_scroll_round
                    + 1
                )

                self.scroll_train_type(
                    boxes["type"],
                    next_round
                )

                self.current_train_scroll_round = (
                    next_round
                )

            points = self.train_slot_points(
                boxes["type"]
            )

            slot_index = int(
                data.get(
                    "slot_index",
                    -1
                )
            )

            if (
                slot_index < 0
                or slot_index >= len(points)
            ):
                return None, None

            x, y = points[
                slot_index
            ]

            self.click(
                x,
                y
            )

            self.sleep(
                self.select_wait
            )

            detail = self.read_train_detail(
                boxes["category"],
                boxes["level"],
                boxes["cost"]
            )

            actual_category = self.normalize_category(
                detail.get(
                    "category",
                    ""
                )
            )

            if actual_category == category:
                return detail, boxes

            # 第一次失配：通常代表使用者手動滾動，
            # 程式內部 round 與實際畫面不同。
            if attempt == 0:
                self.log_info(
                    f"Train 定位失配：預期 {category}，"
                    f"實際 {actual_category or '未知'}；"
                    "重開 Train 校正滾動位置"
                )

                train_on = self.reset_train_view()

                if not train_on:
                    return None, None

                self.current_train_scroll_round = 0

                # 下一次 for attempt 會從頂端重新依 mapping 定位。
                continue

            self.log_info(
                f"Train 定位失敗：預期 {category}，"
                f"實際 {actual_category or '未知'}"
            )

            return None, None

        return None, None

    def update_train_memory(
        self,
        category,
        detail
    ):
        category = self.normalize_category(
            category
        )

        data = self.train_table.get(
            category
        )

        if not data:
            return

        data.update(
            {
                "level": detail.get(
                    "level"
                ),
                "cost": detail.get(
                    "cost"
                ),
                "level_raw": detail.get(
                    "level_raw",
                    ""
                ),
                "cost_raw": detail.get(
                    "cost_raw",
                    ""
                ),
                "requirement_category": detail.get(
                    "requirement_category"
                ),
                "requirement_level": detail.get(
                    "requirement_level"
                ),
            }
        )

    def set_requirement_wait_cost(
        self,
        root_target_category,
        dependency_category,
        dependency_level,
        cost
    ):
        """
        記住「目前要滿足前置條件，下一步至少需要多少錢」。

        之後 Trigger 仍會照設定間隔讀 global money，
        但在 money < 這個成本時，不再反覆進 Train / 點紅字 / 跳前置。
        """

        root_target_category = self.normalize_category(
            root_target_category
        )

        data = self.train_table.get(
            root_target_category
        )

        if not data:
            return

        data["requirement_wait_cost"] = cost
        data["requirement_wait_category"] = (
            self.normalize_category(
                dependency_category
            )
        )
        data["requirement_wait_level"] = (
            dependency_level
        )

    def clear_requirement_wait_cost(
        self,
        root_target_category
    ):
        root_target_category = self.normalize_category(
            root_target_category
        )

        data = self.train_table.get(
            root_target_category
        )

        if not data:
            return

        data.pop(
            "requirement_wait_cost",
            None
        )
        data.pop(
            "requirement_wait_category",
            None
        )
        data.pop(
            "requirement_wait_level",
            None
        )

    def choose_priority_target(
        self,
        current_money
    ):
        """
        第一優先：使用者勾選項目。

        一般項目：
            current_money >= cost 才進 BUY。

        有前置條件：
            第一次先進 resolver 取得 prerequisite 的「下一步成本」。
            一旦已取得 requirement_wait_cost，
            後續 money 未達該成本時只等待，不再每次 Trigger 都點紅字。
        """

        for category in self.priority_categories:
            data = self.train_table.get(
                category
            )

            if not data:
                continue

            requirement_wait_cost = data.get(
                "requirement_wait_cost"
            )

            if requirement_wait_cost is not None:
                if current_money >= requirement_wait_cost:
                    return category

                # 已知前置條件下一步成本，但錢還不夠：
                # 直接等待 global money，不進 Train UI。
                continue

            if data.get(
                "requirement_category"
            ):
                # 第一次尚不知道 prerequisite 的實際下一步成本，
                # 進 resolver 一次取得並快取。
                return category

            cost = data.get(
                "cost"
            )

            # 掃描時 cost 未知，仍需進現場確認一次。
            if cost is None:
                return category

            if current_money >= cost:
                return category

        return None

    def choose_cap_fallback_target(
        self,
        current_money
    ):
        """
        money 到 cap 才啟用。

        從「未勾選」項目中選擇目前買得起且最便宜的一項，
        目的只是在避免資源溢出。
        """

        priority_set = set(
            self.priority_categories
        )

        candidates = []

        for category in self.discovery_order:
            if category in priority_set:
                continue

            data = self.train_table.get(
                category
            )

            if not data:
                continue

            cost = data.get(
                "cost"
            )

            if (
                cost is None
                or cost <= 0
                or cost > current_money
            ):
                continue

            candidates.append(
                (
                    cost,
                    category
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item[0]
        )

        return candidates[0][1]

    def mark_auto_jump_position(
        self,
        category
    ):
        """
        點紅字後遊戲會自動跳到 prerequisite。
        如果 mapping 裡有該項目，就同步目前 scroll round。
        """

        data = self.train_table.get(
            self.normalize_category(
                category
            )
        )

        if data:
            self.current_train_scroll_round = int(
                data.get(
                    "scroll_round",
                    self.current_train_scroll_round
                )
            )

    def satisfy_selected_requirement(
        self,
        category,
        required_level,
        boxes,
        depth=0,
        root_target_category=None
    ):
        """
        目前畫面已經選到 prerequisite category。

        只要：
            LV < required_level
            且錢夠
        就連續升級。

        若 prerequisite 自己也有前置條件，
        繼續點它的紅字自動跳轉，最多遞迴 5 層。
        """

        if depth > 5:
            return False

        category = self.normalize_category(
            category
        )

        if root_target_category is None:
            root_target_category = category

        root_target_category = (
            self.normalize_category(
                root_target_category
            )
        )

        for _ in range(100):
            detail = self.read_train_detail(
                boxes["category"],
                boxes["level"],
                boxes["cost"]
            )

            live_category = self.normalize_category(
                detail.get(
                    "category",
                    ""
                )
            )

            if live_category != category:
                return False

            live_level = detail.get(
                "level"
            )

            if live_level is None:
                return False

            self.update_train_memory(
                category,
                detail
            )

            if live_level >= required_level:
                self.clear_requirement_wait_cost(
                    root_target_category
                )
                return True

            sub_requirement = detail.get(
                "requirement_category"
            )

            sub_requirement_level = detail.get(
                "requirement_level"
            )

            if (
                sub_requirement
                and sub_requirement_level is not None
            ):
                # 點紅字 → 遊戲自動跳到更底層 prerequisite。
                self.click(
                    boxes["cost"]
                )

                self.sleep(
                    self.select_wait
                )

                jumped = self.read_train_detail(
                    boxes["category"],
                    boxes["level"],
                    boxes["cost"]
                )

                jumped_category = self.normalize_category(
                    jumped.get(
                        "category",
                        ""
                    )
                )

                expected_sub_requirement = (
                    self.normalize_category(
                        sub_requirement
                    )
                )

                # 紅字 prerequisite 名稱可能被 OCR 誤讀。
                # 例如「決鬥」可能被讀成「決門」。
                #
                # 因此：
                # - required LV 仍使用紅字 OCR 的數字。
                # - dependency 名稱以「點紅字後實際跳到的 train_category」為準。
                # - 完全沒跳 / 還停在原 category 才視為失敗。
                if (
                    not jumped_category
                    or jumped_category == category
                ):
                    return False

                if (
                    jumped_category
                    != expected_sub_requirement
                ):
                    self.log_info(
                        "前置條件名稱 OCR 差異："
                        f"文字辨識={expected_sub_requirement or sub_requirement}，"
                        f"實際跳轉={jumped_category}；"
                        "採用實際跳轉項目"
                    )

                self.mark_auto_jump_position(
                    jumped_category
                )

                if not self.satisfy_selected_requirement(
                    jumped_category,
                    sub_requirement_level,
                    boxes,
                    depth + 1,
                    root_target_category
                ):
                    return False

                # 下層條件完成後，回到目前 prerequisite。
                detail_again, boxes_again = (
                    self.locate_train_item(
                        category
                    )
                )

                if (
                    not detail_again
                    or not boxes_again
                ):
                    return False

                boxes = boxes_again
                continue

            live_cost = detail.get(
                "cost"
            )

            if (
                live_cost is None
                or live_cost <= 0
            ):
                return False

            # UI 最終安全判斷：
            # prerequisite 也會紅，所以只有「數字 cost + 紅色」才代表沒錢。
            if detail.get(
                "insufficient_money"
            ):
                self.set_requirement_wait_cost(
                    root_target_category,
                    category,
                    required_level,
                    live_cost
                )

                self.log_info(
                    f"Train 金額不足：{category} "
                    f"cost={live_cost:,}，"
                    "train_money 為紅色；停止 PAY"
                )
                return False

            current, _cap, _raw = (
                self.read_global_money()
            )

            if current is None:
                return False

            if current < live_cost:
                self.set_requirement_wait_cost(
                    root_target_category,
                    category,
                    required_level,
                    live_cost
                )
                return False

            self.click(
                boxes["pay"]
            )

            self.sleep(
                self.purchase_wait
            )

            after_detail = self.read_train_detail(
                boxes["category"],
                boxes["level"],
                boxes["cost"]
            )

            after_category = self.normalize_category(
                after_detail.get(
                    "category",
                    ""
                )
            )

            if after_category != category:
                return False

            after_level = after_detail.get(
                "level"
            )

            # PAY 後等級沒有增加 = 點擊未生效。
            # 立即停止，避免同一按鈕無限重複點擊。
            if (
                after_level is None
                or after_level <= live_level
            ):
                self.log_info(
                    f"Train PAY 無進展：{category} "
                    f"Lv.{live_level} -> "
                    f"{'?' if after_level is None else f'Lv.{after_level}'}；"
                    "停止本輪避免迴圈"
                )
                return False

            self.update_train_memory(
                category,
                after_detail
            )

            self.read_global_money()

        return False

    def resolve_train_requirement(
        self,
        target_category,
        detail,
        boxes
    ):
        """
        target 顯示紅字前置條件時：

        1. 點紅字。
        2. 遊戲自動跳到 prerequisite。
        3. 把 prerequisite 升到指定 LV。
        4. 再回原 target。

        不會把「LV.5」錯當成 cost=5。
        """

        requirement_category = detail.get(
            "requirement_category"
        )

        requirement_level = detail.get(
            "requirement_level"
        )

        if (
            not requirement_category
            or requirement_level is None
        ):
            return False

        # 直接點紅字，不點 PAY。
        self.click(
            boxes["cost"]
        )

        self.sleep(
            self.select_wait
        )

        jumped = self.read_train_detail(
            boxes["category"],
            boxes["level"],
            boxes["cost"]
        )

        jumped_category = self.normalize_category(
            jumped.get(
                "category",
                ""
            )
        )

        requirement_category = self.normalize_category(
            requirement_category
        )

        # 第一層 prerequisite 也採相同規則：
        # 紅字 OCR 的名稱只作參考，真正 dependency 以點擊後
        # train_category 實際跳到的項目為準。
        if (
            not jumped_category
            or jumped_category
            == self.normalize_category(
                target_category
            )
        ):
            return False

        if jumped_category != requirement_category:
            self.log_info(
                "前置條件名稱 OCR 差異："
                f"文字辨識={requirement_category}，"
                f"實際跳轉={jumped_category}；"
                "採用實際跳轉項目"
            )

        self.mark_auto_jump_position(
            jumped_category
        )

        # 把剛跳到的 prerequisite 即時 LV / cost 寫回 mapping。
        self.update_train_memory(
            jumped_category,
            jumped
        )

        if not self.satisfy_selected_requirement(
            jumped_category,
            requirement_level,
            boxes,
            depth=0,
            root_target_category=target_category
        ):
            return False

        self.clear_requirement_wait_cost(
            target_category
        )

        # prerequisite 完成後，回原 target。
        # 若原 target 在上方，reset_train_view 會用 Train OFF→ON，
        # 不會正常經過 menu。
        target_detail, target_boxes = (
            self.locate_train_item(
                target_category
            )
        )

        if (
            not target_detail
            or not target_boxes
        ):
            return False

        return True

    def buy_train_item(
        self,
        category
    ):
        """
        PAY 安全鏈：

        一般：
            定位 → category/LV/cost → money >= cost → PAY

        前置條件：
            偵測紅字「達到 XXX LV.N」
            → 點紅字自動跳到 XXX
            → 先補 prerequisite
            → 回原 target
            → 再重新判斷是否可 PAY
        """

        category = self.normalize_category(
            category
        )

        for _ in range(3):
            detail, boxes = self.locate_train_item(
                category
            )

            if (
                not detail
                or not boxes
            ):
                return False

            live_category = self.normalize_category(
                detail.get(
                    "category",
                    ""
                )
            )

            if live_category != category:
                return False

            live_level = detail.get(
                "level"
            )

            if live_level is None:
                return False

            self.update_train_memory(
                category,
                detail
            )

            # 前置條件紅字：先處理 dependency。
            if detail.get(
                "requirement_category"
            ):
                if not self.resolve_train_requirement(
                    category,
                    detail,
                    boxes
                ):
                    return False

                # prerequisite 已補完。
                # 重新定位 / OCR 原 target，再進下一輪。
                continue

            live_cost = detail.get(
                "cost"
            )

            if live_cost is None:
                raw = str(
                    detail.get(
                        "cost_raw",
                        ""
                    )
                ).strip()

                if (
                    raw
                    and raw not in self.reported_unknown_train_money
                ):
                    self.reported_unknown_train_money.add(
                        raw
                    )

                    self.log_info(
                        "[Train Money Unknown] "
                        f"{category}: raw='{raw}'"
                    )

                # 不知道價格 / 條件時絕對不點 PAY。
                return False

            if live_cost <= 0:
                return False

            # UI 最終安全判斷：
            # prerequisite 文字也可能是紅色，但 prerequisite 已在上方分支處理；
            # 到這裡只有「可解析數字 cost + 紅色」才代表金額不足。
            if detail.get(
                "insufficient_money"
            ):
                self.log_info(
                    f"Train 金額不足：{category} "
                    f"cost={live_cost:,}，"
                    "train_money 為紅色；不點 PAY"
                )
                return False

            current, _cap, _raw = (
                self.read_global_money()
            )

            if (
                current is None
                or current < live_cost
            ):
                return False

            self.click(
                boxes["pay"]
            )

            self.sleep(
                self.purchase_wait
            )

            after_detail = self.read_train_detail(
                boxes["category"],
                boxes["level"],
                boxes["cost"]
            )

            after_category = self.normalize_category(
                after_detail.get(
                    "category",
                    ""
                )
            )

            if after_category != category:
                return False

            after_level = after_detail.get(
                "level"
            )

            # 真正成功至少應該看到 LV 上升。
            # 若 PAY 沒造成任何進展，不能回 True，否則 auto_buy_tick
            # 會把同一項目當成「已購買」而持續下一輪。
            if (
                after_level is None
                or after_level <= live_level
            ):
                self.log_info(
                    f"Train PAY 無進展：{category} "
                    f"Lv.{live_level} -> "
                    f"{'?' if after_level is None else f'Lv.{after_level}'}；"
                    "停止本輪避免迴圈"
                )
                return False

            self.update_train_memory(
                category,
                after_detail
            )

            self.read_global_money()

            return True

        return False

    def auto_buy_tick(self):
        """
        一次 Trigger 內允許連續 BUY。

        邏輯：
        1. 每次 BUY 後重新 OCR money。
        2. BUY 後該項目的 LV / cost 已由 buy_train_item() 更新。
        3. 只要仍有勾選項目買得起，就繼續 BUY。
        4. 勾選項目都買不起時，正常停止。
        5. 只有 money >= cap 時，才允許買未勾選項目避免溢出。

        max_buy_per_trigger 只是防止 OCR / UI 異常造成無限迴圈；
        正常情況會在錢不夠時自然結束。
        """

        max_buy_per_trigger = 100
        buy_count = 0

        while (
            buy_count
            < max_buy_per_trigger
        ):
            current, cap, _raw = (
                self.read_global_money()
            )

            if (
                current is None
                or cap is None
            ):
                return

            # 第一優先：使用者勾選項目。
            target = (
                self.choose_priority_target(
                    current
                )
            )

            if target:
                bought = self.buy_train_item(
                    target
                )

                if not bought:
                    return

                buy_count += 1

                # PAY 後重新讀 money + 使用更新後 cost；
                # 如果還買得起，下一輪立即繼續。
                continue

            # 勾選項目都買不起：
            # 平常直接停止，不亂花錢。
            if not (
                self.cap_fallback_enabled
                and current >= cap
            ):
                return

            # 只有 money 到 cap 才動未勾選項目。
            fallback = (
                self.choose_cap_fallback_target(
                    current
                )
            )

            if not fallback:
                return

            bought = self.buy_train_item(
                fallback
            )

            if not bought:
                return

            buy_count += 1

        # 安全上限到達就把控制權交還 TaskExecutor。
        return

    # =========================================================
    # Mapping LOG
    # =========================================================

    @staticmethod
    def format_money(
        value
    ):
        if value is None:
            return "?"

        return f"{value:,}"

    def log_train_table(self):
        lines = [
            "",
            "========== 訓練掃描對應表 ==========",
        ]

        for index, category in enumerate(
            self.discovery_order,
            start=1
        ):
            data = self.train_table[
                category
            ]

            level = data.get(
                "level"
            )

            cost = data.get(
                "cost"
            )

            requirement_category = data.get(
                "requirement_category"
            )

            requirement_level = data.get(
                "requirement_level"
            )

            level_text = (
                f"Lv.{level}"
                if level is not None
                else "Lv.?"
            )

            requirement_wait_cost = data.get(
                "requirement_wait_cost"
            )

            if (
                requirement_category
                and requirement_level is not None
            ):
                cost_text = (
                    f"需要 {requirement_category} "
                    f"Lv.{requirement_level}"
                )

                if requirement_wait_cost is not None:
                    cost_text += (
                        f" / 下一步 {self.format_money(requirement_wait_cost)}"
                    )
            else:
                cost_text = (
                    self.format_money(
                        cost
                    )
                    if cost is not None
                    else "待現場確認"
                )

            lines.append(
                f"{index:02d}. "
                f"{category} | "
                f"{level_text} | "
                f"{cost_text}"
            )

        lines.append(
            "===================================="
        )

        self.log_info(
            "\n".join(
                lines
            )
        )

    # =========================================================
    # Main
    # =========================================================

    def run(self):
        """
        TriggerTask 每次只做一輪。

        第一次：
            建 mapping → 掃完後只 reset 一次到頂端 → BUY tick

        後續：
            直接 BUY tick。
            BUY tick / locate_train_item 會自行確認 train 狀態，
            不會每個 trigger 都先關閉/重開訓練頁。
        """

        self.apply_user_config()

        if (
            not self.train_scan_completed
            or not self.train_table
        ):
            if not self.scan_all_train_types():
                return

        self.auto_buy_tick()

