import time
from pathlib import Path

from ok import TriggerTask
from ok.feature.Box import Box
from ok.util.color import find_color_rectangles

from src.task.BaseWoGTask import BaseWoGTask
from ok_tasks.AutoTraining import AutoTraining


class AutoStageFreezeTask(BaseWoGTask, TriggerTask):
    FORCE_FLAG_NAME = "force_stage_freeze.flag"
    """
    關卡 Freeze 自動恢復。

    邏輯：
    - 每 30 秒讀一次全域 money OCR。
    - money 讀不到：重置比較狀態。
    - money 有變化：更新基準並把不變次數歸零。
    - money 連續不變 2 次：判定可能關卡 Freeze。
    - 自動進入關卡頁，定位目前綠色關卡，點 stage_enter1 / stage_enter2 重進。

    共用：
    - 斷線重連：繼承 BaseWoGTask，全域 offline cooldown / reconnect 設定照常生效。
    - money OCR：直接沿用 AutoTraining._read_global_money_once() 與其解析器。
    """

    # =========================================================
    # 直接共用 AutoTraining 的 money / anchor helper
    # =========================================================

    full_screen_box = AutoTraining.full_screen_box
    find_fullscreen = AutoTraining.find_fullscreen
    find_menu_anchor = AutoTraining.find_menu_anchor
    get_anchor_offset = AutoTraining.get_anchor_offset
    relative_box = AutoTraining.relative_box

    _ocr_piece_text = staticmethod(AutoTraining._ocr_piece_text)
    parse_compact_number = staticmethod(AutoTraining.parse_compact_number)
    parse_money_pair = AutoTraining.parse_money_pair
    make_color_range = staticmethod(AutoTraining.make_color_range)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.name = "關卡 Freeze 自動恢復"
        self.description = (
            "每 30 秒檢查金幣；金幣連續兩次沒有變化時，"
            "自動進入關卡頁並點目前關卡重新進入。"
        )

        self.default_config = {
            "_enabled": True,
            "金幣檢查間隔": 30.0,
            "連續不變次數": 2,
        }

        self.config_description = {
            "金幣檢查間隔":
                "多久讀一次 money OCR，單位秒。預設 30 秒。",
            "連續不變次數":
                "同一金幣數值連續出現幾次後判定可能 Freeze。預設 2 次。",
        }

        self.trigger_interval = 30.0

        # 跟 AutoTraining 的 money OCR 保持同一 threshold。
        self.ocr_threshold = 0.10
        self.last_money_raw = ""
        self.current_money = None
        self.money_cap = None

        # Freeze monitor runtime state
        self.last_freeze_money = None
        self.unchanged_count = 0

        # Stage UI timing
        self.stage_open_wait = 1.5
        self.stage_enter_wait = 3.0

        # stage_on 的實測 RGB
        self.stage_on_rgb = (251, 228, 29)
        self.stage_on_tolerance = 8
        self.stage_on_min_ratio = 0.001

        # 目前關卡綠色標記的實測 RGB
        self.stage_pos_rgb = (135, 233, 7)
        self.stage_pos_tolerance = 10
        self.stage_pos_min_ratio = 0.001

        # Template matching
        self.stage_template_threshold = 0.62

        # PowerShell 強制測試旗標。
        # 建立 force_stage_freeze.flag 後，不等 money freeze，直接跑 recover_stage()。
        self._force_run_requested = False

    # =========================================================
    # Trigger scheduling
    # =========================================================

    def force_flag_paths(self):
        """
        支援兩個位置：
        1. 目前工作目錄
        2. 原始碼專案根目錄（ok_tasks 的上一層）

        開發環境通常兩者都會指向 D:\\ok-WoG。
        """
        paths = [
            Path.cwd() / self.FORCE_FLAG_NAME,
        ]

        try:
            project_root = Path(__file__).resolve().parents[1]
            candidate = project_root / self.FORCE_FLAG_NAME

            if candidate not in paths:
                paths.append(candidate)
        except Exception:
            pass

        return paths

    def get_force_flag_path(self):
        for path in self.force_flag_paths():
            try:
                if path.exists():
                    return path
            except OSError:
                continue

        return None

    def consume_force_flag(self):
        path = self.get_force_flag_path()

        if path:
            try:
                path.unlink()
            except OSError as exc:
                self.log_debug(
                    f"[Stage Freeze] 強制旗標刪除失敗: {exc}"
                )

        requested = self._force_run_requested
        self._force_run_requested = False

        return bool(path or requested)

    def should_trigger(self):
        config = getattr(self, "config", {})

        try:
            interval = float(
                config.get(
                    "金幣檢查間隔",
                    30.0
                )
            )
        except (TypeError, ValueError):
            interval = 30.0

        self.trigger_interval = max(
            1.0,
            interval
        )

        # 先照正常流程走 BaseWoGTask：
        # 全域 offline 檢查仍會執行，而且原本的 Trigger interval 也維持。
        normal_trigger = super().should_trigger()

        # 強制旗標存在時，不必等 30 秒 interval。
        # TaskExecutor 下一輪巡到此 Task 即可執行。
        if self.get_force_flag_path():
            self._force_run_requested = True
            return True

        return normal_trigger

    def get_unchanged_limit(self):
        config = getattr(self, "config", {})

        try:
            limit = int(
                config.get(
                    "連續不變次數",
                    2
                )
            )
        except (TypeError, ValueError):
            limit = 2

        return max(
            1,
            limit
        )

    # =========================================================
    # Money OCR
    # =========================================================

    def read_money_once(self):
        """
        直接共用 AutoTraining 的單次 money OCR。

        注意：
        不使用 AutoTraining.read_global_money() 的 menu recovery，
        因為 Freeze monitor 的規則是：
        「這輪讀不到 money 就直接重置計數」。
        """
        return AutoTraining._read_global_money_once(self)

    def reset_money_watch(self):
        self.last_freeze_money = None
        self.unchanged_count = 0

    # =========================================================
    # Feature helpers
    # =========================================================

    def safe_feature_box(self, name):
        try:
            return self.get_box_by_name(name)
        except Exception:
            return None

    def safe_relative_box(
        self,
        name,
        dx,
        dy,
        padding=0
    ):
        ref = self.safe_feature_box(name)

        if not ref:
            return None

        return Box(
            max(0, ref.x + dx - padding),
            max(0, ref.y + dy - padding),
            ref.width + padding * 2,
            ref.height + padding * 2,
            name=name
        )

    def safe_find_one(
        self,
        name,
        box,
        threshold=None
    ):
        if not self.safe_feature_box(name):
            return None

        if threshold is None:
            threshold = self.stage_template_threshold

        try:
            return self.find_one(
                name,
                box=box,
                threshold=threshold
            )
        except Exception:
            return None

    # =========================================================
    # Stage page
    # =========================================================

    def get_menu_runtime_offset(self):
        menu = self.find_menu_anchor()

        if not menu:
            return None, None, None

        dx, dy = self.get_anchor_offset(
            menu,
            "menu"
        )

        return menu, dx, dy

    def stage_is_on(
        self,
        dx,
        dy
    ):
        stage_on_box = self.safe_relative_box(
            "stage_on",
            dx,
            dy
        )

        if not stage_on_box:
            return False

        color_range = self.make_color_range(
            self.stage_on_rgb,
            self.stage_on_tolerance
        )

        try:
            ratio = self.calculate_color_percentage(
                color_range,
                stage_on_box
            )
        except Exception:
            ratio = 0

        if ratio >= self.stage_on_min_ratio:
            return True

        # RGB 沒命中時再用 stage_on template 補一次。
        search_box = self.safe_relative_box(
            "stage_on",
            dx,
            dy,
            padding=18
        )

        if not search_box:
            return False

        return bool(
            self.safe_find_one(
                "stage_on",
                search_box,
                threshold=0.60
            )
        )

    def open_stage_page(self):
        menu, dx, dy = self.get_menu_runtime_offset()

        if not menu:
            self.log_info(
                "[Stage Freeze] 找不到 menu，無法進入關卡頁"
            )
            return None

        if self.stage_is_on(dx, dy):
            stage_tab = self.safe_relative_box(
                "stage_tab",
                dx,
                dy
            )

            if stage_tab:
                return stage_tab

        # 優先點 stage OFF template 的位置。
        stage_button = self.safe_relative_box(
            "stage",
            dx,
            dy
        )

        # 如果 stage 沒標註，stage_on 與 stage 是同一位置，
        # 直接使用 stage_on reference 當 click target。
        if not stage_button:
            stage_button = self.safe_relative_box(
                "stage_on",
                dx,
                dy
            )

        if not stage_button:
            self.log_info(
                "[Stage Freeze] 找不到 stage / stage_on 標註"
            )
            return None

        self.click(
            stage_button
        )

        self.sleep(
            self.stage_open_wait
        )

        # UI 切換後重新抓 menu，避免 runtime offset 已變。
        menu, dx, dy = self.get_menu_runtime_offset()

        if not menu:
            self.log_info(
                "[Stage Freeze] 點 stage 後找不到 menu"
            )
            return None

        if not self.stage_is_on(dx, dy):
            self.log_info(
                "[Stage Freeze] 點 stage 後未確認 stage_on"
            )
            return None

        stage_tab = self.safe_relative_box(
            "stage_tab",
            dx,
            dy
        )

        if not stage_tab:
            self.log_info(
                "[Stage Freeze] 找不到 stage_tab 標註"
            )
            return None

        return stage_tab

    # =========================================================
    # Current stage locating
    # =========================================================

    def stage_green_range(self):
        return self.make_color_range(
            self.stage_pos_rgb,
            self.stage_pos_tolerance
        )

    def green_ratio(self, box):
        if not box:
            return 0.0

        try:
            return self.calculate_color_percentage(
                self.stage_green_range(),
                box
            )
        except Exception:
            return 0.0

    def find_stage_template_variant(
        self,
        stage_tab
    ):
        """
        優先：
            stage_pos1 template + 綠色驗證
            stage_pos2 template + 綠色驗證

        回傳：
            ("stage_pos1", runtime_box)
            ("stage_pos2", runtime_box)
            (None, None)
        """
        for name in (
            "stage_pos1",
            "stage_pos2"
        ):
            found = self.safe_find_one(
                name,
                stage_tab,
                threshold=self.stage_template_threshold
            )

            if not found:
                continue

            # template 命中後再配合目前關卡綠色確認。
            # 搜尋框稍微放大，避免綠光超出模板 bbox。
            check_box = Box(
                max(0, found.x - 8),
                max(0, found.y - 8),
                found.width + 16,
                found.height + 16
            )

            ratio = self.green_ratio(
                check_box
            )

            if ratio >= self.stage_pos_min_ratio:
                self.log_info(
                    f"[Stage Freeze] {name} 模板 + 綠色配對成功 "
                    f"(green={ratio:.4f})"
                )
                return name, found

        return None, None

    def find_stage_green_fallback(
        self,
        stage_tab
    ):
        """
        stage_pos1 / stage_pos2 template 都失敗時，
        只在 stage_tab 內搜尋 RGB (135,233,7) 附近的綠色區塊。
        """
        try:
            candidates = find_color_rectangles(
                self.frame,
                self.stage_green_range(),
                min_width=2,
                min_height=2,
                max_width=120,
                max_height=120,
                threshold=0.05,
                box=stage_tab
            )
        except Exception as exc:
            self.log_debug(
                f"[Stage Freeze] 綠色 fallback 搜尋失敗: {exc}"
            )
            return None

        if not candidates:
            return None

        # stage_tab 內最大的綠色 connected area
        # 通常就是目前關卡的綠色 halo / marker。
        candidates = sorted(
            candidates,
            key=lambda b: b.width * b.height,
            reverse=True
        )

        return candidates[0]

    def choose_variant_for_color_box(
        self,
        color_box
    ):
        """
        純顏色 fallback 沒有 template variant 資訊時，
        以 reference bbox 尺寸選較接近的 stage_pos1 / stage_pos2。
        """
        choices = []

        for name in (
            "stage_pos1",
            "stage_pos2"
        ):
            ref = self.safe_feature_box(
                name
            )

            if not ref:
                continue

            score = (
                abs(ref.width - color_box.width)
                + abs(ref.height - color_box.height)
            )

            choices.append(
                (score, name)
            )

        if not choices:
            return None

        choices.sort(
            key=lambda item: item[0]
        )

        return choices[0][1]

    # =========================================================
    # stage_pos -> stage_enter
    # =========================================================

    def get_stage_enter_box(
        self,
        pos_name,
        runtime_pos
    ):
        if pos_name not in (
            "stage_pos1",
            "stage_pos2"
        ):
            return None

        enter_name = (
            "stage_enter1"
            if pos_name == "stage_pos1"
            else "stage_enter2"
        )

        ref_pos = self.safe_feature_box(
            pos_name
        )
        ref_enter = self.safe_feature_box(
            enter_name
        )

        if (
            not ref_pos
            or not ref_enter
        ):
            return None

        dx = runtime_pos.x - ref_pos.x
        dy = runtime_pos.y - ref_pos.y

        return Box(
            max(0, ref_enter.x + dx),
            max(0, ref_enter.y + dy),
            ref_enter.width,
            ref_enter.height,
            name=enter_name
        )

    def recover_stage(self):
        self.log_info(
            "[Stage Freeze] 開始重新進入目前關卡"
        )

        stage_tab = self.open_stage_page()

        if not stage_tab:
            return False

        # 1. template + green
        pos_name, runtime_pos = (
            self.find_stage_template_variant(
                stage_tab
            )
        )

        # 2. RGB fallback
        if not runtime_pos:
            runtime_pos = (
                self.find_stage_green_fallback(
                    stage_tab
                )
            )

            if runtime_pos:
                pos_name = (
                    self.choose_variant_for_color_box(
                        runtime_pos
                    )
                )

                self.log_info(
                    "[Stage Freeze] stage_pos template 未命中，"
                    f"改用 RGB fallback；variant={pos_name or 'unknown'}"
                )

        if not runtime_pos:
            self.log_info(
                "[Stage Freeze] stage_tab 內找不到目前綠色關卡"
            )
            return False

        enter_box = self.get_stage_enter_box(
            pos_name,
            runtime_pos
        )

        if not enter_box:
            self.log_info(
                "[Stage Freeze] 無法由 stage_pos 算出 stage_enter"
            )
            return False

        self.log_info(
            f"[Stage Freeze] 點擊 {enter_box.name} 重新進入關卡"
        )

        self.click(
            enter_box
        )

        self.sleep(
            self.stage_enter_wait
        )

        return True

    # =========================================================
    # Main
    # =========================================================

    def run(self):
        # PowerShell 強制測試：
        # New-Item ".\\force_stage_freeze.flag" -ItemType File -Force
        #
        # 這條路徑完全跳過 money freeze 判定，
        # 直接測 stage -> stage_on -> stage_tab -> stage_pos -> stage_enter。
        if self.consume_force_flag():
            self.log_info(
                "[Stage Freeze] 偵測到強制測試旗標：直接執行關卡重新進入"
            )

            success = self.recover_stage()

            if success:
                self.log_info(
                    "[Stage Freeze] 強制測試完成：已點目前關卡"
                )
            else:
                self.log_info(
                    "[Stage Freeze] 強制測試失敗：請查看上方定位 LOG"
                )

            # 強制測試不沿用舊 money 比較狀態。
            self.reset_money_watch()
            return

        current, _cap, raw = (
            self.read_money_once()
        )

        # 使用者指定：
        # 沒有偵測到 money -> 重置記數。
        if current is None:
            if (
                self.last_freeze_money is not None
                or self.unchanged_count != 0
            ):
                self.log_info(
                    "[Stage Freeze] Money OCR 失敗，重置 Freeze 計數"
                )

            self.reset_money_watch()
            return

        # 第一次成功讀到 money：只建立基準。
        if self.last_freeze_money is None:
            self.last_freeze_money = current
            self.unchanged_count = 0

            self.log_info(
                f"[Stage Freeze] Money baseline={current:,} raw='{raw}'"
            )
            return

        # money 有變化：代表關卡仍正常產出。
        if current != self.last_freeze_money:
            previous = self.last_freeze_money
            self.last_freeze_money = current
            self.unchanged_count = 0

            self.log_debug(
                f"[Stage Freeze] Money changed "
                f"{previous:,} -> {current:,}"
            )
            return

        # money 和上次完全相同。
        self.unchanged_count += 1

        limit = self.get_unchanged_limit()

        self.log_info(
            f"[Stage Freeze] Money unchanged "
            f"{current:,} ({self.unchanged_count}/{limit})"
        )

        if self.unchanged_count < limit:
            return

        self.log_info(
            "[Stage Freeze] 金幣連續未變，判定可能關卡 Freeze"
        )

        success = self.recover_stage()

        if success:
            self.log_info(
                "[Stage Freeze] 已點目前關卡，重新進入完成"
            )
        else:
            self.log_info(
                "[Stage Freeze] 本次重新進入失敗，稍後重新監測"
            )

        # 一次 recovery 嘗試後重新建立 money baseline。
        # 若遊戲仍 freeze，之後會再次累積到門檻再嘗試。
        self.reset_money_watch()
