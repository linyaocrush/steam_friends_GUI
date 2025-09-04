import flet as ft
import requests
import json
import re
import csv
from datetime import datetime
import os
import threading


class SettingsManager:
    def __init__(self):
        self.settings_file = 'steam_settings.json'
        self.defaults = {
            'api_key': '', 'steam_id': '', 'proxy': '',
            'window_width': 900, 'window_height': 700
        }
    
    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return {**self.defaults, **json.load(f)}
        except: pass
        return self.defaults.copy()
    
    def save_settings(self, settings):
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False


class SteamFriendsFixedGUI:
    def __init__(self):
        self.steam_web_api = self.steam_id = None
        self.friends = 0
        self.friends_list = {}
        self.friend_data = []
        
        self.base_url = 'https://api.steampowered.com'
        self.urls = {
            'friends': 'https://api.steampowered.com/ISteamUser/GetFriendList/v0001/',
            'summaries': 'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/',
            'remove_friend': 'https://api.steampowered.com/ISteamUser/RemoveFriend/v1/'
        }
        
        self.sess = requests.Session()
        self.sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.avatar_dir = 'avatar_cache'
        os.makedirs(self.avatar_dir, exist_ok=True)

    def set_proxy(self, proxy):
        if proxy:
            self.sess.proxies.update({'http': proxy, 'https': proxy})

    def get_friend_list(self):
        response = self.sess.get(self.urls['friends'], params={'key': self.steam_web_api, 'steamid': self.steam_id})
        
        if response.status_code == 200:
            friends = response.json()['friendslist']['friends']
            self.friends_list = {f['steamid']: f['friend_since'] for f in friends}
            self.friends = len(self.friends_list)
            return True
            
        status_map = {
            401: "Unauthorized，请检查你的steam隐私设置",
            403: "403 Forbidden，请检查你的web_api和id的值",
            500: "服务器内部错误，请检查你的steamid的值"
        }
        raise Exception(status_map.get(response.status_code, f"收到未处理的状态码：{response.status_code}"))

    def get_friends_summaries(self):
        steam_ids = list(self.friends_list.keys())
        
        for i in range(0, len(steam_ids), 100):
            batch = ','.join(steam_ids[i:i+100])
            response = self.sess.get(self.urls['summaries'], params={'key': self.steam_web_api, 'steamids': batch})
            
            if response.status_code != 200:
                raise Exception("429 Too Many Requests" if response.status_code == 429 else response.text)
            
            for user in response.json()['response']['players']:
                self.friend_data.append({
                    'avatar': self.download_avatar(user['avatar'], user['steamid']),
                    'name': re.sub(r'[|\-+:"\'\n\r]', '`', user['personaname']),
                    'steamid': user['steamid'],
                    'is_friend': '✅',
                    'bfd': datetime.fromtimestamp(self.friends_list[user['steamid']]).strftime('%Y-%m-%d %H:%M:%S'),
                    'removed_time': '',
                    'remark': ''
                })

    def read_friends_data(self):
        """读取好友数据"""
        try:
            with open('friends_data.csv', 'r', encoding='utf-8-sig', newline='') as f:
                return list(csv.DictReader(f))
        except: return []

    def save_friends_data(self, data):
        """保存好友数据"""
        if not data: return
        with open('friends_data.csv', 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    
    def download_avatar(self, url, steamid):
        """下载头像"""
        filepath = os.path.join(self.avatar_dir, f"{steamid}_{os.path.basename(url)}")
        
        if not os.path.exists(filepath):
            try:
                with open(filepath, 'wb') as f:
                    f.write(self.sess.get(url, timeout=10).content)
            except: return url
        return filepath

    def update_friends_list(self):
        """更新好友列表"""
        self.get_friend_list()
        self.get_friends_summaries()
        
        data = self.read_friends_data()
        current = {f['steamid']: f for f in self.friend_data}
        data_dict = {d['steamid']: d for d in data}
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        updated = []
        
        # 处理当前好友
        for steamid, friend_info in current.items():
            if steamid in data_dict:
                data_dict[steamid].update(friend_info)
                updated.append(data_dict.pop(steamid))
            else:
                updated.append(friend_info)
        
        # 处理已删除的好友
        for d in data_dict.values():
            if d['is_friend'] == '✅':
                d.update({'is_friend': '❌', 'removed_time': d.get('removed_time') or now})
            updated.append(d)
        
        self.save_friends_data(updated)
        return updated

    def delete_non_friends(self):
        """删除非好友记录"""
        data = self.read_friends_data()
        if not data: return []
        current = [d for d in data if d['is_friend'] == '✅']
        self.save_friends_data(current)
        return current

    def remove_friend(self, friend_steamid):
        """删除好友"""
        response = self.sess.post(self.urls['remove_friend'], params={
            'key': self.steam_web_api,
            'steamid': self.steam_id,
            'friendid': friend_steamid
        })
        
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            raise Exception("Unauthorized，请检查你的steam隐私设置")
        elif response.status_code == 403:
            raise Exception("403 Forbidden，请检查你的web_api和id的值")
        elif response.status_code == 500:
            raise Exception("服务器内部错误，请检查你的steamid的值")
        else:
            raise Exception(f"删除好友失败，状态码：{response.status_code}")
    
    def get_user_info(self, friend_code):
        """通过好友代码获取用户信息"""
        # 将好友代码转换为SteamID64
        steamid64 = self._friend_code_to_steamid(friend_code)
        
        if not steamid64:
            raise Exception("无效的好友代码")
        
        url = f"{self.base_url}/ISteamUser/GetPlayerSummaries/v2/"
        params = {
            'key': self.steam_web_api,
            'steamids': steamid64
        }
        
        response = self._make_request(url, params)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'response' in data and 'players' in data['response'] and len(data['response']['players']) > 0:
                user_info = data['response']['players'][0]
                # 获取游戏数量
                user_info['game_count'] = self.get_user_game_count(steamid64)
                return user_info
            else:
                raise Exception("未找到用户信息")
        elif response.status_code == 401:
            raise Exception("API密钥无效或已过期")
        elif response.status_code == 500:
            raise Exception("Steam服务器内部错误")
        else:
            raise Exception(f"获取用户信息失败: HTTP {response.status_code}")
    
    def get_user_game_count(self, steamid64):
        """获取用户游戏数量"""
        url = f"{self.base_url}/IPlayerService/GetOwnedGames/v0001/"
        params = {
            'key': self.steam_web_api,
            'steamid': steamid64,
            'include_played_free_games': '1',
            'format': 'json'
        }
        
        try:
            response = self._make_request(url, params)
            
            if response.status_code == 200:
                data = response.json()
                if 'response' in data and 'game_count' in data['response']:
                    return data['response']['game_count']
                else:
                    return 0
            else:
                # 如果获取游戏数量失败，返回0
                return 0
        except Exception as e:
            print(f"获取游戏数量失败: {e}")
            return 0
    
    def send_friend_request(self, steamid64):
        """发送好友申请"""
        url = f"{self.base_url}/ISteamUser/AddFriend/v1/"
        params = {
            'key': self.steam_web_api,
            'steamid': self.steam_id,
            'friendid': steamid64
        }
        
        response = self._make_request(url, params)
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            raise Exception("API密钥无效或已过期")
        elif response.status_code == 403:
            raise Exception("权限不足，无法发送好友申请")
        elif response.status_code == 500:
            raise Exception("Steam服务器内部错误")
        else:
            raise Exception(f"发送好友申请失败: HTTP {response.status_code}")
    
    def _make_request(self, url, params):
        """发送HTTP请求"""
        return self.sess.get(url, params=params)
    
    def _friend_code_to_steamid(self, friend_code):
        """将好友代码转换为SteamID64"""
        try:
            # 移除可能的格式字符
            friend_code = friend_code.strip().replace('-', '').replace(' ', '')
            
            # 检查是否是数字格式（直接是SteamID64）
            if friend_code.isdigit() and len(friend_code) == 17:
                return friend_code
            
            # 检查是否是SteamID格式（STEAM_0:0:12345678）
            if friend_code.startswith('STEAM_'):
                parts = friend_code.split(':')
                if len(parts) == 3:
                    y = int(parts[1])
                    z = int(parts[2])
                    steamid64 = str(76561197960265728 + (z * 2) + y)
                    return steamid64
            
            # 检查是否是纯数字（可能是SteamID32或其他格式）
            if friend_code.isdigit():
                # 尝试将数字转换为SteamID64
                # SteamID64 = 76561197960265728 + SteamID32
                steamid32 = int(friend_code)
                steamid64 = str(76561197960265728 + steamid32)
                return steamid64
            
            # 检查是否是好友代码格式（FCABC-DEF-GHI）
            if len(friend_code) >= 8 and friend_code.isalnum():
                # Steam好友代码转换算法
                try:
                    # 如果是17位数字，直接返回
                    if len(friend_code) == 17:
                        return friend_code
                    
                    # 尝试解析为Steam好友代码
                    # Steam好友代码使用Base58编码
                    
                    # Base58字符集
                    base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
                    
                    # 反转字符串以便计算
                    friend_code_reversed = friend_code[::-1]
                    
                    # Base58解码
                    code_num = 0
                    for i, char in enumerate(friend_code_reversed):
                        if char in base58_chars:
                            code_num += base58_chars.index(char) * (58 ** i)
                        else:
                            return None
                    
                    # 转换为SteamID64
                    # SteamID64 = 76561197960265728 + code_num
                    steamid64 = str(76561197960265728 + code_num)
                    return steamid64
                    
                except Exception as e:
                    return None
            
            return None
        except Exception as e:
            return None


class SteamFriendsApp:
    def __init__(self):
        self.steam_friends, self.settings_manager = SteamFriendsFixedGUI(), SettingsManager()
        self.settings, self.page = self.settings_manager.load_settings(), None
        self.selected_friends = {}  # 存储选中的好友
        self.current_user_info = None  # 当前查询的用户信息
    
    def _setup_steam_api(self):
        """设置Steam API配置"""
        self.steam_friends.steam_web_api = self.api_key_input.value
        self.steam_friends.steam_id = self.steam_id_input.value
        self.steam_friends.set_proxy(self.proxy_input.value)
    
    def _disable_buttons(self, buttons):
        """禁用指定的按钮"""
        for btn in buttons:
            btn.disabled = True
        self.page.update()
    
    def _enable_buttons(self, buttons):
        """启用指定的按钮"""
        for btn in buttons:
            btn.disabled = False
        self.page.update()
    
    def _show_progress(self, message="处理中..."):
        """显示进度条和状态信息"""
        self.progress_bar.visible = True
        self.progress_bar.value = None
        self.status_text.value = message
        self.page.update()
    
    def _hide_progress(self):
        """隐藏进度条"""
        self.progress_bar.visible = False
        self.page.update()
    
    def _run_thread_task(self, task_func, finish_func):
        """运行线程任务的通用方法"""
        def wrapper():
            try:
                result = task_func()
                self.page.run_thread(lambda: finish_func(True, result))
            except Exception as e:
                self.page.run_thread(lambda: finish_func(False, str(e)))
        
        threading.Thread(target=wrapper, daemon=True).start()
    
    def _validate_inputs(self, *required_inputs):
        """验证必需的输入字段"""
        missing = []
        for input_field in required_inputs:
            if not input_field.value:
                missing.append(input_field.label)
        
        if missing:
            self.status_text.value = f"请填写: {', '.join(missing)}"
            self.page.update()
            return False
        return True

    def main(self, page: ft.Page):
        self.page = page
        page.title = "Steam好友管理工具"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.window_width = self.settings.get('window_width', 900)
        page.window_height = self.settings.get('window_height', 700)
        page.window_resizable = True

        # 创建UI组件
        self.create_ui_components()

    def create_ui_components(self):
        """创建UI组件"""
        # 设置页面主题与背景
        self.page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE, use_material3=True)
        self.page.bgcolor = ft.Colors.with_opacity(0.1, ft.Colors.BLUE_GREY_50)

        # 创建输入框
        def create_text_field(label, hint, value_key, password=False):
            return ft.TextField(
                label=label, hint_text=hint, password=password,
                value=self.settings.get(value_key, ''), width=280, dense=True,
                border_radius=10, filled=True, bgcolor=ft.Colors.WHITE,
                border_color=ft.Colors.BLUE_200
            )

        self.api_key_input = create_text_field("Steam Web API Key", "输入你的Steam Web API密钥", 'api_key', True)
        self.steam_id_input = create_text_field("Steam ID", "输入你的Steam ID", 'steam_id')
        self.proxy_input = create_text_field("代理地址 (可选)", "http://127.0.0.1:7890", 'proxy')
        
        # 好友功能组件
        self.friend_code_input = create_text_field("好友代码", "输入Steam好友代码或ID", 'friend_code')
        # 调整好友代码输入框的宽度以适应左右布局
        self.friend_code_input.width = 260
        self.user_info_display = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Text("用户信息", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=ft.Colors.BLUE_700)
                    ], spacing=8),
                    alignment=ft.alignment.center
                ),
                ft.Divider(height=1, thickness=1, color=ft.Colors.BLUE_200),
                ft.Container(
                    content=ft.Text("请输入好友代码查询用户信息", size=12, color=ft.Colors.GREY_600),
                    alignment=ft.alignment.center
                )
            ], spacing=8),
            padding=ft.padding.symmetric(horizontal=15, vertical=20),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_50),
            border_radius=10,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            width=700,
            height=200
        )

        self.progress_bar = ft.ProgressBar(
            width=400, visible=False,
            color=ft.Colors.BLUE_500,
            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.BLUE_100)
        )
        self.status_text = ft.Text("就绪", size=14, weight=ft.FontWeight.W_500)
        self.sort_ascending = True
        self.sort_indicator = ft.Icon(ft.Icons.ARROW_UPWARD, size=16)

        # 创建数据表格（等分布局）
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Checkbox()),
                ft.DataColumn(ft.Text("头像", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700), numeric=True),
                ft.DataColumn(ft.Text("昵称", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)),
                ft.DataColumn(ft.Text("Steam ID", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)),
                ft.DataColumn(ft.Text("状态", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700), numeric=True),
                ft.DataColumn(
                    ft.Row([ft.Text("成为好友时间", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700), self.sort_indicator], spacing=5),
                    tooltip="点击排序", on_sort=lambda e: self._toggle_sort()
                ),
                ft.DataColumn(ft.Text("删除时间", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)),
                ft.DataColumn(ft.Text("备注", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)),
            ],
            rows=[], expand=True, column_spacing=20,
            data_row_min_height=50, data_row_max_height=80,
            border_radius=10,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            bgcolor=ft.Colors.WHITE,
            data_row_color={ft.ControlState.HOVERED: ft.Colors.with_opacity(0.1, ft.Colors.BLUE_100)},
            heading_row_color=ft.Colors.with_opacity(0.2, ft.Colors.BLUE_100),
            horizontal_lines=ft.border.BorderSide(1, ft.Colors.BLUE_50),
            vertical_lines=ft.border.BorderSide(1, ft.Colors.BLUE_50)
        )

        self.scroll_view = ft.Column([self.data_table], scroll=ft.ScrollMode.AUTO, 
                                   expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        # 创建按钮（带样式）
        def create_button(text, handler, color=ft.Colors.BLUE_500, width=150):
            return ft.ElevatedButton(
                text=text, on_click=handler, width=width, height=40,
                style=ft.ButtonStyle(
                    bgcolor=color, color=ft.Colors.WHITE,
                    shape=ft.RoundedRectangleBorder(radius=8), elevation=2,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8)
                )
            )

        self.update_button = create_button("更新好友列表", self.update_friends)
        self.delete_button = create_button("删除非好友记录", self.delete_non_friends, ft.Colors.RED_500)
        self.remove_friend_button = create_button("删除选中好友", self.remove_selected_friends, ft.Colors.RED_700)
        self.save_settings_button = create_button("保存设置", self.save_current_settings, ft.Colors.GREEN_500)
        self.refresh_avatar_button = create_button("刷新头像", self.refresh_avatars)
        self.refresh_avatar_button.visible = False
        
        # 好友功能按钮
        self.query_user_button = create_button("查询用户", self.query_user_info, ft.Colors.PURPLE_500, 130)
        self.add_friend_button = create_button("添加好友", self.send_friend_request, ft.Colors.GREEN_600, 130)
        self.add_friend_button.disabled = True  # 初始状态禁用
        
        # 全选复选框
        self.select_all_checkbox = ft.Checkbox(
            label="全选",
            on_change=self._toggle_select_all,
            active_color=ft.Colors.BLUE_500
        )

        # 创建帮助链接
        api_help = ft.TextButton(
            "获取Steam API Key",
            on_click=lambda e: self.open_url("https://steamcommunity.com/dev/apikey"),
            style=ft.ButtonStyle(color=ft.Colors.BLUE_600)
        )
        steamid_help = ft.TextButton(
            "查找Steam ID",
            on_click=lambda e: self.open_url("https://steamid.io/"),
            style=ft.ButtonStyle(color=ft.Colors.BLUE_600)
        )

        # 主容器（渐变背景）
        main_container = ft.Container(
            content=ft.Column([
                # 标题区域（蓝色渐变）
                ft.Container(
                    content=ft.Text(
                        "Steam好友管理工具", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, font_family="PingFang SC"
                    ),
                    padding=20, alignment=ft.alignment.center,
                    gradient=ft.LinearGradient(
                        begin=ft.alignment.top_center, end=ft.alignment.bottom_center,
                        colors=[ft.Colors.BLUE_600, ft.Colors.with_opacity(0.8, ft.Colors.BLUE_400)]
                    ),
                    border_radius=ft.border_radius.only(top_left=10, top_right=10)
                ),
                # 输入区域
                ft.Container(
                    content=ft.Column([
                        ft.Row([api_help, steamid_help], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([
                            self.api_key_input, self.steam_id_input, self.proxy_input
                        ], spacing=15, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([
                            self.update_button, self.delete_button, self.remove_friend_button, 
                            self.refresh_avatar_button, self.save_settings_button
                        ], spacing=15, alignment=ft.MainAxisAlignment.CENTER),
                        ft.Row([self.select_all_checkbox], alignment=ft.MainAxisAlignment.CENTER),
                        # 好友功能区域（可折叠）
                        ft.Divider(),
                        ft.Container(
                            content=ft.ExpansionPanelList(
                                controls=[
                                    ft.ExpansionPanel(
                                        header=ft.Container(
                                            content=ft.Row([
                                                ft.Text("添加好友", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                                                ft.Icon(ft.Icons.PERSON_ADD, size=20, color=ft.Colors.BLUE_700)
                                            ], spacing=10),
                                            padding=ft.padding.symmetric(horizontal=15, vertical=10)
                                        ),
                                        content=ft.Container(
                                            content=ft.Column([
                                                # 左右布局：添加好友输入和用户信息显示
                                                ft.Container(
                                                    content=ft.Row([
                                                        # 左侧：好友代码输入区域（紧凑布局）
                                                        ft.Container(
                                                            content=ft.Column([
                                                                ft.Container(
                                                                    content=ft.Text("添加好友", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
                                                                    alignment=ft.alignment.center
                                                                ),
                                                                ft.Container(
                                                                    content=self.friend_code_input,
                                                                    width=200
                                                                )
                                                            ], spacing=8),
                                                            width=220,
                                                            alignment=ft.alignment.center
                                                        ),
                                                        # 右侧：用户信息显示区域（占满剩余空间）
                                                        ft.Container(
                                                            content=self.user_info_display,
                                                            expand=True,
                                                            alignment=ft.alignment.center
                                                        )
                                                    ], spacing=15, alignment=ft.MainAxisAlignment.START),
                                                    alignment=ft.alignment.center
                                                ),
                                                # 按钮区域
                                                ft.Container(
                                                    content=ft.Row([
                                                        self.query_user_button,
                                                        ft.Container(width=20),  # 间距
                                                        self.add_friend_button
                                                    ], alignment=ft.MainAxisAlignment.CENTER),
                                                    alignment=ft.alignment.center,
                                                    padding=ft.padding.only(top=15)
                                                )
                                            ], spacing=15),
                                            padding=ft.padding.symmetric(horizontal=20, vertical=15)
                                        )
                                    )
                                ],
                                expand=False,  # 默认折叠
                                divider_color=ft.Colors.BLUE_200,
                                spacing=0
                            ),
                            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_50),
                            border_radius=12,
                            border=ft.border.all(1, ft.Colors.BLUE_200),
                            margin=ft.margin.symmetric(vertical=5)
                        ),
                        self.progress_bar,
                        ft.Container(content=self.status_text, alignment=ft.alignment.center, padding=5)
                    ], spacing=15),
                    padding=20, bgcolor=ft.Colors.WHITE,
                    border_radius=ft.border_radius.only(bottom_left=10, bottom_right=10)
                ),
                # 数据表格区域
                ft.Container(
                    content=ft.Column([self.scroll_view], expand=True),
                    expand=True, margin=ft.margin.only(top=10), padding=10,
                    bgcolor=ft.Colors.WHITE, border_radius=10,
                    border=ft.border.all(1, ft.Colors.BLUE_100)
                )
            ], spacing=0),
            margin=20, border_radius=10,
            shadow=ft.BoxShadow(
                spread_radius=1, blur_radius=10,
                color=ft.Colors.with_opacity(0.2, ft.Colors.BLUE_GREY_200),
                offset=ft.Offset(0, 2)
            )
        )

        # 页面背景（蓝白渐变）
        gradient_bg = ft.Container(
            content=main_container,
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left, end=ft.alignment.bottom_right,
                colors=[
                    ft.Colors.BLUE_50,
                    ft.Colors.with_opacity(0.7, ft.Colors.BLUE_100),
                    ft.Colors.with_opacity(0.5, ft.Colors.BLUE_50),
                    ft.Colors.with_opacity(0.3, ft.Colors.WHITE)
                ]
            )
        )

        self.page.add(gradient_bg)
        self.page.on_resize = lambda e: self.settings.update({
            'window_width': self.page.window_width, 'window_height': self.page.window_height
        })
        self.load_existing_data()

    def open_url(self, url):
        """打开URL"""
        import webbrowser
        webbrowser.open(url)

    def save_current_settings(self, e=None):
        """保存当前设置"""
        settings = {
            'api_key': self.api_key_input.value,
            'steam_id': self.steam_id_input.value,
            'proxy': self.proxy_input.value,
            'window_width': self.page.window_width,
            'window_height': self.page.window_height
        }
        
        success = self.settings_manager.save_settings(settings)
        self.status_text.value = "设置已保存" if success else "保存设置失败"
        self.page.update()

    def load_existing_data(self):
        try:
            data = self.steam_friends.read_friends_data()
            has_data = bool(data)
            if has_data:
                self._update_data_table()
            self.status_text.value = f"已加载 {len(data)} 条记录" if has_data else "暂无数据，请先更新好友列表"
            self.refresh_avatar_button.visible = has_data
            self.page.update()
        except Exception as e:
            self.status_text.value = f"加载数据失败: {str(e)}"
            self.refresh_avatar_button.visible = False
            self.page.update()

    def _toggle_sort(self):
        """切换排序方向"""
        self.sort_ascending = not self.sort_ascending
        
        # 更新排序指示器
        if self.sort_ascending:
            self.sort_indicator.name = ft.Icons.ARROW_UPWARD
        else:
            self.sort_indicator.name = ft.Icons.ARROW_DOWNWARD
        
        # 重新加载并排序数据
        self._update_data_table()
    
    def _update_remark(self, steamid, new_remark):
        """更新好友备注"""
        try:
            data = self.steam_friends.read_friends_data()
            if not data: return
            
            for item in data:
                if item['steamid'] == steamid and item.get('remark', '') != new_remark:
                    item['remark'] = new_remark
                    self.steam_friends.save_friends_data(data)
                    self.status_text.value = f"已更新 {item['name']} 的备注"
                    self.page.update()
                    break
        except Exception as e:
            self.status_text.value = f"更新备注失败: {str(e)}"
            self.page.update()

    def _open_steam_profile(self, steamid):
        """打开Steam个人主页"""
        try:
            import webbrowser
            profile_url = f"https://steamcommunity.com/profiles/{steamid}"
            webbrowser.open(profile_url)
            self.status_text.value = f"正在打开Steam个人主页..."
            self.page.update()
        except Exception as e:
            self.status_text.value = f"打开个人主页失败: {str(e)}"
            self.page.update()

    def _toggle_friend_selection(self, steamid, is_selected):
        """切换好友选择状态"""
        self.selected_friends[steamid] = is_selected
        # 更新全选复选框状态
        data = self.steam_friends.read_friends_data()
        if data:
            all_selected = all(self.selected_friends.get(item['steamid'], False) for item in data)
            self.select_all_checkbox.value = all_selected
            self.page.update()

    def _toggle_select_all(self, e):
        """切换全选状态"""
        data = self.steam_friends.read_friends_data()
        if not data: return
        
        is_selected = e.control.value
        for item in data:
            self.selected_friends[item['steamid']] = is_selected
        
        # 重新渲染数据表格以更新复选框状态
        self._update_data_table()

    def _update_data_table(self):
        """更新数据表格"""
        self.data_table.rows.clear()
        data = self.steam_friends.read_friends_data()
        if not data: return self.page.update()
        
        # 排序数据
        try:
            data.sort(key=lambda x: datetime.strptime(x['bfd'], '%Y-%m-%d %H:%M:%S'), 
                     reverse=not self.sort_ascending)
        except: pass
        
        for item in data:
            # 选择复选框
            select_checkbox = ft.Checkbox(
                value=self.selected_friends.get(item['steamid'], False),
                on_change=lambda e, sid=item['steamid']: self._toggle_friend_selection(sid, e.control.value)
            )
            
            # 头像 - 居中显示
            avatar = ft.Container(
                content=ft.Image(
                    src=item['avatar'], 
                    width=36, 
                    height=36, 
                    fit=ft.ImageFit.COVER, 
                    border_radius=18
                ),
                width=40, 
                height=40, 
                border_radius=20, 
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor=ft.Colors.BLUE_50,
                alignment=ft.alignment.center
            )
            
            # 昵称 - 加粗显示并居中
            name_text = ft.Text(
                item['name'], 
                weight=ft.FontWeight.W_500,
                size=14,
                text_align=ft.TextAlign.CENTER,
                width=120
            )
            
            # Steam ID - 超链接
            steam_id_text = ft.TextButton(
                text=item['steamid'], 
                style=ft.ButtonStyle(
                    color=ft.Colors.BLUE_600,
                    text_style=ft.TextStyle(
                        font_family="monospace",
                        size=12,
                        decoration=ft.TextDecoration.UNDERLINE
                    )
                ),
                on_click=lambda e, sid=item['steamid']: self._open_steam_profile(sid)
            )
            
            # 好友状态 - 文本显示并居中
            status_text = ft.Text(
                item['is_friend'], 
                size=12,
                weight=ft.FontWeight.W_500,
                text_align=ft.TextAlign.CENTER,
                width=60
            )
            
            # 时间显示 - 格式化并居中
            bfd_text = ft.Text(item['bfd'], size=12, text_align=ft.TextAlign.CENTER, width=120) if item['bfd'] else ft.Text("-", size=12, text_align=ft.TextAlign.CENTER, width=120)
            removed_text = ft.Text(item['removed_time'], size=12, text_align=ft.TextAlign.CENTER, width=120) if item['removed_time'] else ft.Text("-", size=12, text_align=ft.TextAlign.CENTER, width=120)
            
            # 备注 - 美化输入框
            remark = ft.TextField(
                value=item['remark'] or '', 
                width=200, 
                height=32, 
                dense=True,
                border=ft.InputBorder.UNDERLINE,
                filled=True,
                text_size=12,
                hint_text="点击添加备注...",
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLUE_50),
                content_padding=ft.padding.only(left=8, right=8, top=8, bottom=4),
                border_color=ft.Colors.BLUE_200,
                focused_border_color=ft.Colors.BLUE_500,
                cursor_color=ft.Colors.BLUE_500,
                on_change=lambda e, sid=item['steamid']: self._update_remark(sid, e.control.value)
            )
            
            self.data_table.rows.append(ft.DataRow([
                ft.DataCell(select_checkbox),
                ft.DataCell(avatar),
                ft.DataCell(name_text),
                ft.DataCell(steam_id_text),
                ft.DataCell(status_text),
                ft.DataCell(bfd_text),
                ft.DataCell(removed_text),
                ft.DataCell(remark)
            ]))
        
        self.page.update()

    def update_friends(self, e):
        """更新好友列表"""
        if not self._validate_inputs(self.api_key_input, self.steam_id_input):
            return
        
        # 禁用按钮并显示进度
        self._disable_buttons([self.update_button, self.delete_button, self.refresh_avatar_button])
        self._show_progress("正在更新好友列表...")
        
        def update_task():
            self._setup_steam_api()
            return self.steam_friends.update_friends_list()
        
        def finish_update(success, result):
            self._enable_buttons([self.update_button, self.delete_button, self.refresh_avatar_button])
            self._hide_progress()
            
            if success:
                self.status_text.value = f"更新完成，共 {len(result)} 条记录"
                self._update_data_table()
                self.refresh_avatar_button.visible = True
            else:
                self.status_text.value = f"更新失败: {result}"
            self.page.update()
        
        self._run_thread_task(update_task, finish_update)



    def delete_non_friends(self, e):
        """删除非好友记录"""
        # 禁用按钮并显示进度
        self._disable_buttons([self.update_button, self.delete_button, self.refresh_avatar_button])
        self._show_progress("正在删除非好友记录...")
        
        def delete_task():
            return self.steam_friends.delete_non_friends()
        
        def finish_delete(success, result):
            self._enable_buttons([self.update_button, self.delete_button, self.refresh_avatar_button])
            self._hide_progress()
            
            if success:
                self.status_text.value = f"已删除非好友记录，剩余 {len(result)} 条记录"
                self._update_data_table()
            else:
                self.status_text.value = f"删除失败: {result}"
            self.page.update()
        
        self._run_thread_task(delete_task, finish_delete)

    def remove_selected_friends(self, e):
        """删除选中的好友"""
        # 获取选中的好友
        selected_steamids = [steamid for steamid, is_selected in self.selected_friends.items() if is_selected]
        
        if not selected_steamids:
            self.status_text.value = "请先选择要删除的好友"
            return self.page.update()
        
        # 确认删除
        def confirm_delete(e):
            if e.control.text == "确定":
                # 禁用按钮并显示进度
                for btn in [self.update_button, self.delete_button, self.remove_friend_button, self.refresh_avatar_button]:
                    btn.disabled = True
                self.progress_bar.visible = True
                self.status_text.value = f"正在删除 {len(selected_steamids)} 个好友..."
                self.page.update()
                
                def delete_task():
                    try:
                        self.steam_friends.steam_web_api = self.api_key_input.value
                        self.steam_friends.steam_id = self.steam_id_input.value
                        self.steam_friends.set_proxy(self.proxy_input.value)
                        
                        success_count = 0
                        failed_friends = []
                        
                        for steamid in selected_steamids:
                            try:
                                if self.steam_friends.remove_friend(steamid):
                                    success_count += 1
                                else:
                                    failed_friends.append(steamid)
                            except Exception as error:
                                failed_friends.append(f"{steamid} ({str(error)})")
                        
                        # 更新本地数据
                        if success_count > 0:
                            data = self.steam_friends.read_friends_data()
                            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            for item in data:
                                if item['steamid'] in selected_steamids and item['is_friend'] == '✅':
                                    item['is_friend'] = '❌'
                                    item['removed_time'] = now
                            
                            self.steam_friends.save_friends_data(data)
                        
                        # 清空选择
                        self.selected_friends.clear()
                        
                        if failed_friends:
                            message = f"成功删除 {success_count} 个好友，失败 {len(failed_friends)} 个：{', '.join(failed_friends[:3])}{'...' if len(failed_friends) > 3 else ''}"
                        else:
                            message = f"成功删除 {success_count} 个好友"
                        
                        self.page.run_thread(lambda: self._finish_remove_friend(True, message))
                    except Exception as e:
                        self.page.run_thread(lambda: self._finish_remove_friend(False, f"删除好友失败: {e}"))
                
                threading.Thread(target=delete_task, daemon=True).start()
            
            # 关闭对话框
            self.page.dialog.open = False
            self.page.update()
        
        # 取消删除
        def cancel_delete(e):
            self.page.dialog.open = False
            self.page.update()
        
        # 显示确认对话框
        dialog = ft.AlertDialog(
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要删除选中的 {len(selected_steamids)} 个好友吗？此操作不可撤销。"),
            actions=[
                ft.TextButton("确定", on_click=confirm_delete),
                ft.TextButton("取消", on_click=cancel_delete)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _finish_remove_friend(self, success, message):
        """完成删除好友后的UI处理"""
        for btn in [self.update_button, self.delete_button, self.remove_friend_button, self.refresh_avatar_button]:
            btn.disabled = False
        self.progress_bar.visible = False
        self.status_text.value = message
        if success:
            self._update_data_table()
        self.page.update()

    def refresh_avatars(self, e):
        """刷新头像"""
        self._disable_buttons([self.refresh_avatar_button])
        self._show_progress("正在刷新头像...")
        
        def refresh_task():
            data = self.steam_friends.read_friends_data()
            if not data:
                return "没有数据需要刷新"
            
            count = 0
            for item in data:
                if item['steamid']:
                    url = f"https://avatars.akamai.steamstatic.com/{item['steamid']}_full.jpg"
                    new_path = self.steam_friends.download_avatar(url, item['steamid'])
                    if new_path != item['avatar']:
                        item['avatar'], count = new_path, count + 1
            
            if count:
                self.steam_friends.save_friends_data(data)
            
            return f"已刷新 {count} 个头像"
        
        def finish_refresh(success, result):
            self._enable_buttons([self.refresh_avatar_button])
            self._hide_progress()
            
            if success:
                self.status_text.value = result
                self._update_data_table()
            else:
                self.status_text.value = f"刷新失败: {result}"
            self.page.update()
        
        self._run_thread_task(refresh_task, finish_refresh)
    
    def query_user_info(self, e):
        """查询用户信息"""
        if not self._validate_inputs(self.api_key_input, self.steam_id_input, self.friend_code_input):
            return
        
        # 禁用按钮并显示进度
        self._disable_buttons([self.query_user_button])
        self._show_progress("正在查询用户信息...")
        
        def query_task():
            self._setup_steam_api()
            return self.steam_friends.get_user_info(self.friend_code_input.value)
        
        def finish_query_user(success, result):
            self._enable_buttons([self.query_user_button])
            self._hide_progress()
            
            if success:
                self.status_text.value = "查询成功"
                self._update_user_info_display(result)
                self.add_friend_button.disabled = False
            else:
                self.status_text.value = f"查询失败: {result}"
                self._reset_user_info_display()
                self.add_friend_button.disabled = True
            self.page.update()
        
        self._run_thread_task(query_task, finish_query_user)
    
    def _update_user_info_display(self, user_info):
        """更新用户信息显示"""
        self.current_user_info = user_info
        user_name = user_info.get('personaname', '未知用户')
        user_status = "在线" if user_info.get('personastate', 0) > 0 else "离线"
        user_avatar = user_info.get('avatarfull', '')
        user_profile_url = f"https://steamcommunity.com/profiles/{user_info.get('steamid', '')}"
        game_count = user_info.get('game_count', 0)
        
        # 处理头像URL，确保有效并下载到本地缓存
        if not user_avatar or user_avatar == '':
            user_avatar = 'https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb.jpg'  # 默认头像
        
        # 下载头像到本地缓存
        steamid = user_info.get('steamid', '')
        if steamid:
            try:
                user_avatar = self.steam_friends.download_avatar(user_avatar, steamid)
            except Exception as e:
                print(f"下载头像失败: {e}")
                # 如果下载失败，使用默认头像
                user_avatar = 'https://avatars.steamstatic.com/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb.jpg'
        
        self.user_info_display.content = ft.Column([
            ft.Text("用户信息", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
            ft.Divider(),
            ft.Row([
                ft.Image(
                    src=user_avatar,
                    width=40,
                    height=40,
                    border_radius=20,
                    error_content=ft.Icon(ft.Icons.PERSON, size=20, color=ft.Colors.GREY_400)
                ),
                ft.Column([
                    ft.Row([
                        ft.Text(user_name, size=14, weight=ft.FontWeight.W_500),
                        ft.Container(
                            content=ft.Text(
                                f"{game_count} 游戏",
                                size=10,
                                color=ft.Colors.WHITE,
                                weight=ft.FontWeight.W_500
                            ),
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            border_radius=8,
                            gradient=ft.LinearGradient(
                                begin=ft.alignment.top_left,
                                end=ft.alignment.bottom_right,
                                colors=[ft.Colors.BLUE_400, ft.Colors.PURPLE_400]
                            ),
                            margin=ft.margin.only(left=8)
                        )
                    ]),
                    ft.Text(f"状态: {user_status}", size=12, color=ft.Colors.GREY_600)
                ], spacing=5)
            ], spacing=10),
            ft.TextButton(
                text="查看Steam个人主页",
                on_click=lambda e: self.open_url(user_profile_url),
                style=ft.ButtonStyle(color=ft.Colors.BLUE_600)
            )
        ], spacing=10)
    
    def _reset_user_info_display(self):
        """重置用户信息显示"""
        self.current_user_info = None
        self.user_info_display.content = ft.Column([
            ft.Text("用户信息", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700),
            ft.Divider(),
            ft.Text("请输入好友代码查询用户信息", size=14, color=ft.Colors.GREY_600)
        ], spacing=10)
    
    def send_friend_request(self, e):
        """发送好友申请"""
        if not self.current_user_info:
            self.status_text.value = "请先查询用户信息"
            return self.page.update()
        
        # 确认发送好友申请
        def confirm_send(e):
            if e.control.text == "确定":
                self._disable_buttons([self.add_friend_button, self.query_user_button])
                self._show_progress("正在发送好友申请...")
                
                def send_task():
                    try:
                        self.steam_friends.steam_web_api = self.api_key_input.value
                        self.steam_friends.steam_id = self.steam_id_input.value
                        self.steam_friends.set_proxy(self.proxy_input.value)
                        
                        steamid64 = self.current_user_info.get('steamid')
                        success = self.steam_friends.send_friend_request(steamid64)
                        
                        if success:
                            return True, "好友申请发送成功"
                        else:
                            return False, "发送好友申请失败"
                    except Exception as ex:
                        return False, f"发送好友申请失败: {str(ex)}"
                
                self._run_thread_task(send_task, self._finish_send_friend)
            
            # 关闭对话框
            self.page.dialog.open = False
            self.page.update()
        
        # 取消发送
        def cancel_send(e):
            self.page.dialog.open = False
            self.page.update()
        
        # 显示确认对话框
        user_name = self.current_user_info.get('personaname', '未知用户')
        dialog = ft.AlertDialog(
            title=ft.Text("确认发送好友申请"),
            content=ft.Text(f"确定要向 {user_name} 发送好友申请吗？"),
            actions=[
                ft.TextButton("确定", on_click=confirm_send),
                ft.TextButton("取消", on_click=cancel_send)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def _finish_send_friend(self, success, message):
        """完成发送好友申请后的UI处理"""
        self._enable_buttons([self.add_friend_button, self.query_user_button])
        self._hide_progress()
        self.status_text.value = message
        self.page.update()


if __name__ == '__main__':
    app = SteamFriendsApp()
    ft.app(target=app.main)