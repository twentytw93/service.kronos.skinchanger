#twentytw93-KronosTeam
import xbmc
import xbmcaddon
import xbmcgui
import time
import json
from datetime import datetime

_last_logged_color = None 

ADDON = xbmcaddon.Addon()

COLOR_SCHEME = {
    "day": "Light",
    "night": "Darkest"
}

xbmc.log("[Kronos Skin Switcher] Boot detected. Waiting for Kodi UI...", xbmc.LOGINFO)

monitor = xbmc.Monitor()

start = time.time()

while not xbmc.getCondVisibility("Window.IsVisible(home)"):
    if monitor.waitForAbort(0.1):
        xbmc.log("[Kronos Skin Switcher] Aborted during home wait", xbmc.LOGINFO)
        raise SystemExit

if monitor.waitForAbort(2.610):  # Buffer after home screen
    xbmc.log("[Kronos Skin Switcher] Aborted during buffer wait", xbmc.LOGINFO)
    raise SystemExit

while xbmc.getCondVisibility("System.HasActiveModalDialog"):
    if monitor.waitForAbort(0.1):
        xbmc.log("[Kronos Skin Switcher] Aborted during modal wait", xbmc.LOGINFO)
        raise SystemExit

if monitor.waitForAbort(1.0): 
    xbmc.log("[Kronos Skin Switcher] Aborted during fade-in", xbmc.LOGINFO)
    raise SystemExit

elapsed = int((time.time() - start) * 1000)
remaining = 16220 - elapsed
if remaining > 0:
    if monitor.waitForAbort(remaining / 1000.0):
        xbmc.log("[Kronos Skin Switcher] Aborted during final wait", xbmc.LOGINFO)
        raise SystemExit

class PlayerMonitor(xbmc.Player):
    def __init__(self, *args, **kwargs):
        super(PlayerMonitor, self).__init__()
        self.is_playing = xbmc.Player().isPlaying()
        self.last_playback_end = 0
        self.cooldown_period = 7
        if self.is_playing:
            xbmc.log("[Kronos Skin Switcher] Initial state: Playing - switching suspended", xbmc.LOGINFO)
        else:
            xbmc.log("[Kronos Skin Switcher] Initial state: Not playing", xbmc.LOGINFO)

    def onPlayBackStarted(self):
        self.is_playing = True
        xbmc.log("[Kronos Skin Switcher] Playback started - switching suspended", xbmc.LOGINFO)

    def onPlayBackEnded(self):
        self.is_playing = False
        self.last_playback_end = time.time()
        xbmc.log("[Kronos Skin Switcher] Playback ended - cooldown period started", xbmc.LOGINFO)

    def onPlayBackStopped(self):
        self.is_playing = False
        self.last_playback_end = time.time()
        xbmc.log("[Kronos Skin Switcher] Playback stopped - cooldown period started", xbmc.LOGINFO)

    def onPlayBackPaused(self):
        self.is_playing = True

    def onPlayBackResumed(self):
        self.is_playing = True

    def in_cooldown(self):
        return (time.time() - self.last_playback_end) < self.cooldown_period


def _jsonrpc(method, params):
    try:
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        resp_str = xbmc.executeJSONRPC(json.dumps(payload))
        data = json.loads(resp_str)
        if isinstance(data, dict) and "error" not in data:
            return data
        xbmc.log(f"[Kronos Skin Switcher] JSON-RPC error: {data}", xbmc.LOGWARNING)
    except Exception as e:
        xbmc.log(f"[Kronos Skin Switcher] JSON-RPC exception: {e}", xbmc.LOGWARNING)
    return None


def get_current_skin_color():
    data = _jsonrpc("Settings.GetSettingValue", {"setting": "lookandfeel.skincolors"})
    try:
        value = data["result"]["value"]
        if isinstance(value, str):
            return value.strip()
    except Exception:
        pass
    return None


def is_home_screen():
    return xbmc.getCondVisibility('Window.IsVisible(home)')


def set_skin_color(color):
    current = get_current_skin_color()
    if current and current.lower() == color.lower():
        xbmc.log(f"[Kronos Skin Switcher] Skin already set to {color}, skipping reload", xbmc.LOGINFO)
        return

    xbmc.log(f"[Kronos Skin Switcher] Switching to {color}", xbmc.LOGINFO)

    ok = _jsonrpc("Settings.SetSettingValue", {
        "setting": "lookandfeel.skincolors",
        "value": color
    })
    if not ok:
        xbmc.log("[Kronos Skin Switcher] Failed to set skin color via JSON-RPC; skipping reload", xbmc.LOGWARNING)
        return

    t0 = time.time()
    applied = False
    while time.time() - t0 < 2.0:
        new_val = get_current_skin_color()
        if new_val and new_val.lower() == color.lower():
            applied = True
            break
        if monitor.waitForAbort(0.1):
            return

    if applied:
        xbmc.log("[Kronos Skin Switcher] Skin color applied", xbmc.LOGINFO)
    else:
        xbmc.log("[Kronos Skin Switcher] Skin color change not confirmed (non-fatal)", xbmc.LOGWARNING)


def get_time_period():
    current_hour = datetime.now().hour
    if 6 <= current_hour < 18:
        return "day"
    return "night"


def get_target_color():
    return COLOR_SCHEME[get_time_period()]


def should_switch_to(target_color):
    global _last_logged_color
    current_color = get_current_skin_color()
    if current_color is None:
        xbmc.log("[Kronos Skin Switcher] Current color unknown (RPC fail); deferring", xbmc.LOGDEBUG)
        return False

    if current_color.lower() == target_color.lower():
        if _last_logged_color != target_color:
            xbmc.log(f"[Kronos Skin Switcher] Already set to {target_color}", xbmc.LOGINFO)
            _last_logged_color = target_color
        return False

    _last_logged_color = None
    return True


if __name__ == '__main__':
    player = PlayerMonitor()
    last_manual_check = time.time()
    last_switch_time = 0
    switch_cooldown = 15

    while not monitor.abortRequested():
        try:
            current_time = time.time()

            if (
                is_home_screen()
                and not xbmc.getCondVisibility("System.HasActiveModalDialog")
                and not player.is_playing
                and not player.in_cooldown()
                and (current_time - last_switch_time) > switch_cooldown
            ):
                target_color = get_target_color()

                if should_switch_to(target_color):
                    set_skin_color(target_color)
                    last_switch_time = current_time

                if current_time - last_manual_check > 17:
                    cur = get_current_skin_color()
                    if cur is not None and cur.lower() != target_color.lower():
                        xbmc.log("[Kronos Skin Switcher] Correcting manual color change", xbmc.LOGINFO)
                        set_skin_color(target_color)
                        last_switch_time = current_time
                    last_manual_check = current_time

            monitor.waitForAbort(3)

        except Exception as e:
            xbmc.log(f"[Kronos Skin Switcher] ERROR: {str(e)}", xbmc.LOGERROR)