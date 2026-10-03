import ctypes
import time

from ok import BaseTask
from ok.feature.Box import Box


class BaseWoGTask(BaseTask):
    """
    WoG 任務共用基底。

    斷線處理採用類似 OK-WW 月卡的設計：
    - 設定放 Global ConfigOption
    - 實際 TriggerTask 以多重繼承使用本類別
    - should_trigger() 會在正常 Trigger 判斷前做共用斷線巡檢
    - 所有子任務共用同一個 60 秒 cooldown
    """

    OFFLINE_CONFIG_NAME = "伺服器重連設定"

    DEFAULT_OFFLINE_CONFIG = {
        "是否檢查斷線": True,
        "檢查 cooldown": 60.0,
        "重連後等待": 10.0,
    }

    # 所有繼承本 Base 的 TriggerTask 共用，
    # 避免 AutoTraining / 倉庫各自每分鐘掃一次。
    _offline_last_check = 0.0
    _offline_processing = False

    offline_threshold = 0.80
    offline_reward_threshold = 0.80
    offline_relative_padding = 35

    # =========================================================
    # Global config
    # =========================================================

    def get_offline_config(self):
        """
        有註冊 Global ConfigOption 時讀全域設定；
        尚未加入 config.py 時也可用預設值運作。
        """

        try:
            config = self.get_global_config(
                self.OFFLINE_CONFIG_NAME
            )
        except Exception:
            config = None

        if not config:
            return dict(
                self.DEFAULT_OFFLINE_CONFIG
            )

        merged = dict(
            self.DEFAULT_OFFLINE_CONFIG
        )
        merged.update(
            config
        )

        return merged

    # =========================================================
    # Windows foreground control
    # =========================================================

    @staticmethod
    def _window_native_hwnd(hwnd_window):
        """盡量從 ok-script 的 hwnd_window 取得 Win32 HWND。"""
        for name in ("top_hwnd", "hwnd", "real_hwnd", "handle"):
            try:
                value = getattr(hwnd_window, name, None)
                if callable(value):
                    value = value()
                value = int(value or 0)
                if value > 0:
                    try:
                        root = int(
                            ctypes.windll.user32.GetAncestor(value, 2) or 0
                        )
                        if root > 0:
                            return root
                    except Exception:
                        pass
                    return value
            except Exception:
                continue
        return 0

    def _window_is_foreground(self, hwnd_window):
        try:
            if hwnd_window.is_foreground():
                return True
        except Exception:
            pass

        hwnd = self._window_native_hwnd(hwnd_window)
        if hwnd <= 0:
            return False

        try:
            return int(ctypes.windll.user32.GetForegroundWindow() or 0) == hwnd
        except Exception:
            return False

    @staticmethod
    def wog_modifier_state():
        """Read current modifier state without changing any key state."""
        user32 = ctypes.windll.user32
        keys = {
            "SHIFT": 0x10,
            "CTRL": 0x11,
            "ALT": 0x12,
            "LWIN": 0x5B,
            "RWIN": 0x5C,
        }
        return {
            name: bool(int(user32.GetAsyncKeyState(vk)) & 0x8000)
            for name, vk in keys.items()
        }

    def _force_window_foreground_win32(self, hwnd_window):
        """Use a minimal ALT-assisted Win32 foreground fallback."""
        hwnd = self._window_native_hwnd(hwnd_window)
        if hwnd <= 0:
            return False

        try:
            user32 = ctypes.windll.user32
            if not user32.IsWindow(hwnd):
                return False

            SW_RESTORE = 9
            VK_MENU = 0x12
            KEYEVENTF_KEYUP = 0x0002

            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)

            modifiers_before = self.wog_modifier_state()
            if not modifiers_before["ALT"]:
                user32.keybd_event(VK_MENU, 0, 0, 0)
                try:
                    time.sleep(0.03)
                finally:
                    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
                    time.sleep(0.03)

                if self.wog_modifier_state()["ALT"]:
                    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return int(user32.GetForegroundWindow() or 0) == hwnd
        except Exception as exc:
            self.log_debug(
                f"WoG Win32 foreground fallback 失敗: {exc}"
            )
            return False

    def wog_ensure_foreground(self):
        """
        顯式把 WoG 遊戲視窗拉到真正 foreground。

        AutoTraining 的 Pynput / wheel mapping 依賴真實前景輸入；
        因此不能只接受工作列閃爍。最多兩輪，最後重新驗證。
        """
        interaction = getattr(self.executor, "interaction", None)
        hwnd_window = getattr(interaction, "hwnd_window", None)
        if hwnd_window is None:
            device_manager = getattr(self.executor, "device_manager", None)
            hwnd_window = getattr(device_manager, "hwnd_window", None)

        if hwnd_window is None:
            return False

        if self._window_is_foreground(hwnd_window):
            return True

        for attempt in range(1, 3):
            result = None
            try:
                result = hwnd_window.bring_to_front()
            except Exception as exc:
                self.log_debug(
                    f"WoG bring_to_front 第 {attempt} 次失敗: {exc}"
                )

            time.sleep(0.15)

            if self._window_is_foreground(hwnd_window):
                return True

            self._force_window_foreground_win32(hwnd_window)
            time.sleep(0.20)

            if self._window_is_foreground(hwnd_window):
                return True

            self.log_info(
                "WoG：前景取得未成功 "
                f"(attempt={attempt}/2, bring_to_front={result})"
            )

        return False

    # =========================================================
    # Windows cursor recovery
    # =========================================================

    @staticmethod
    def _is_set_cursor_pos_error(exc):
        """
        只處理 Windows SetCursorPos 的瞬間性失敗。
        其他程式錯誤一律原樣拋出，不吞掉。
        """

        if exc is None:
            return False

        if "SetCursorPos" in str(exc):
            return True

        try:
            return any(
                "SetCursorPos" in str(arg)
                for arg in getattr(exc, "args", ())
            )
        except Exception:
            return False

    def _recover_cursor_focus(self):
        """
        SetCursorPos 失敗時：
        重新把遊戲視窗帶到前景，稍等後重試原操作。
        """

        try:
            self.wog_ensure_foreground()
        except Exception as exc:
            self.log_debug(
                f"SetCursorPos recovery foreground 失敗: {exc}"
            )

        # 使用父類 sleep，避免任何子類自訂 sleep 造成遞迴。
        time.sleep(0.30)

    def _run_cursor_operation_with_retry(
        self,
        operation_name,
        operation,
        *args,
        **kwargs
    ):
        """
        SetCursorPos 專用 retry。

        第一次失敗後重新 focus 並重做同一操作。
        最多 retry 2 次（總共嘗試 3 次）。

        只有 SetCursorPos 會進 retry；
        其他 exception 直接 raise。
        """

        max_attempts = 3

        for attempt in range(
            1,
            max_attempts + 1
        ):
            try:
                return operation(
                    *args,
                    **kwargs
                )

            except Exception as exc:
                if not self._is_set_cursor_pos_error(
                    exc
                ):
                    raise

                if attempt >= max_attempts:
                    self.log_info(
                        f"{operation_name}：SetCursorPos "
                        f"連續失敗 {max_attempts} 次，"
                        "略過這次滑鼠操作，等待後續畫面重新校正"
                    )

                    # 不讓瞬間性的 Windows 游標錯誤殺掉整個 TriggerTask。
                    return None

                self.log_info(
                    f"{operation_name}：SetCursorPos 失敗，"
                    f"重新聚焦並重試 ({attempt}/{max_attempts - 1})"
                )

                self._recover_cursor_focus()

        return None

    def click(
        self,
        *args,
        **kwargs
    ):
        """
        所有 WoG TriggerTask 共用的 click SetCursorPos recovery。
        """

        return self._run_cursor_operation_with_retry(
            "click",
            super().click,
            *args,
            **kwargs
        )

    def scroll(
        self,
        *args,
        **kwargs
    ):
        """
        所有 WoG TriggerTask 共用的 scroll SetCursorPos recovery。

        AutoTraining 的滾輪操作最容易碰到 Windows
        SetCursorPos 瞬間失敗，因此在這層統一重試。
        """

        return self._run_cursor_operation_with_retry(
            "scroll",
            super().scroll,
            *args,
            **kwargs
        )

    # =========================================================
    # Shared scheduler hook
    # =========================================================

    def should_trigger(self):
        """
        每次原本 TriggerTask 開始判斷前，只做一次共用 offline 檢查。

        - 沒有 offline：直接繼續原本 task。
        - 有 offline：完整處理 offline / reward，
          處理完固定再等 10 秒，然後仍然繼續原本 task。

        不會因為處理 offline 就取消本輪原 task。
        """

        if not getattr(self, "_wog_startup_foreground_done", False):
            try:
                self.wog_ensure_foreground()
            except Exception as exc:
                self.log_debug(
                    f"WoG startup foreground 失敗，繼續 Task: {exc}"
                )
            finally:
                self._wog_startup_foreground_done = True

            time.sleep(0.15)

        handled = self.check_offline_common()

        if handled:
            self.log_info(
                "斷線共用處理完成：等待 10 秒後繼續原本 Task"
            )

            # 額外的 task-resume settle time。
            # 這 10 秒是在 offline/reward 都處理完之後。
            super().sleep(
                10.0
            )

        return super().should_trigger()

    # =========================================================
    # Offline common helpers
    # =========================================================

    def _offline_full_screen_box(self):
        return Box(
            0,
            0,
            self.width,
            self.height
        )

    def _offline_find_fullscreen(
        self,
        name,
        threshold=0.80
    ):
        return self.find_one(
            name,
            box=self._offline_full_screen_box(),
            threshold=threshold
        )

    def _offline_find_menu_anchor(self):
        return self._offline_find_fullscreen(
            "menu",
            threshold=0.80
        )

    def _offline_get_menu_offset(
        self,
        menu
    ):
        reference = self.get_box_by_name(
            "menu"
        )

        return (
            menu.x - reference.x,
            menu.y - reference.y
        )

    def _offline_relative_box(
        self,
        name,
        dx,
        dy,
        padding=0
    ):
        ref = self.get_box_by_name(
            name
        )

        x = max(
            0,
            ref.x + dx - padding
        )
        y = max(
            0,
            ref.y + dy - padding
        )

        width = ref.width + padding * 2
        height = ref.height + padding * 2

        return Box(
            x,
            y,
            width,
            height,
            name=name
        )

    def _offline_find_relative(
        self,
        name,
        dx,
        dy,
        padding=35,
        threshold=0.80
    ):
        return self.find_one(
            name,
            box=self._offline_relative_box(
                name,
                dx,
                dy,
                padding=padding
            ),
            threshold=threshold
        )

    def _offline_click_relative(
        self,
        name,
        dx,
        dy
    ):
        self.click(
            self._offline_relative_box(
                name,
                dx,
                dy
            )
        )

    # =========================================================
    # Offline flow
    # =========================================================

    def check_offline_common(self):
        """
        平常最多每 60 秒全畫面搜尋一次 offline。

        找到：
            offline（全畫面模板）
            → menu runtime anchor
            → offline_confirm（menu 相對位置）
            → sleep 10 秒
            → 重新找 menu
            → offline_reward（menu 相對區域模板）
            → offline_reward_confirm（menu 相對位置）

        回傳：
            True  = 本輪有偵測並處理 offline
            False = 本輪沒有需要處理的 offline

        注意：
        should_trigger() 收到 True 後不會取消原 Task，
        而是再等 10 秒後繼續原 Task。
        """

        cls = BaseWoGTask

        if cls._offline_processing:
            return True

        config = self.get_offline_config()

        if not config.get(
            "是否檢查斷線",
            True
        ):
            return False

        try:
            cooldown = float(
                config.get(
                    "檢查 cooldown",
                    60.0
                )
            )
        except (
            TypeError,
            ValueError
        ):
            cooldown = 60.0

        cooldown = max(
            1.0,
            cooldown
        )

        now = time.monotonic()

        if (
            cls._offline_last_check > 0
            and now - cls._offline_last_check < cooldown
        ):
            return False

        # 「有沒有找到」都算一次日常巡檢。
        cls._offline_last_check = now

        offline = self._offline_find_fullscreen(
            "offline",
            threshold=self.offline_threshold
        )

        if not offline:
            return False

        cls._offline_processing = True

        try:
            self.log_info(
                "偵測到 offline：開始共用斷線處理"
            )

            menu = self._offline_find_menu_anchor()

            if not menu:
                self.log_info(
                    "偵測到 offline，但找不到 menu；結束本次共用處理"
                )
                return True

            dx, dy = (
                self._offline_get_menu_offset(
                    menu
                )
            )

            self._offline_click_relative(
                "offline_confirm",
                dx,
                dy
            )

            try:
                reconnect_wait = float(
                    config.get(
                        "重連後等待",
                        10.0
                    )
                )
            except (
                TypeError,
                ValueError
            ):
                reconnect_wait = 10.0

            reconnect_wait = max(
                0.0,
                reconnect_wait
            )

            self.log_info(
                f"已點 offline_confirm，等待 {reconnect_wait:g} 秒"
            )

            # 直接使用 TriggerTask/BaseTask 原生 sleep；
            # 不再觸發任何 offline 檢查。
            super().sleep(
                reconnect_wait
            )

            # 下一頁 UI 重新渲染，所以一定重新抓 menu。
            menu = self._offline_find_menu_anchor()

            if not menu:
                self.log_info(
                    "重連後找不到 menu；等待下一輪任務重新確認"
                )
                return True

            dx, dy = (
                self._offline_get_menu_offset(
                    menu
                )
            )

            reward = self._offline_find_relative(
                "offline_reward",
                dx,
                dy,
                padding=self.offline_relative_padding,
                threshold=self.offline_reward_threshold
            )

            if not reward:
                self.log_info(
                    "重連完成：未偵測到 offline_reward"
                )
                return True

            self.log_info(
                "偵測到 offline_reward：領取離線獎勵"
            )

            self._offline_click_relative(
                "offline_reward_confirm",
                dx,
                dy
            )

            return True

        finally:
            cls._offline_processing = False
