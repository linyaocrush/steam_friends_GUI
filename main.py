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
        
        self.urls = {
            'friends': 'https://api.steampowered.com/ISteamUser/GetFriendList/v0001/',
            'summaries': 'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/'
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
            with open('friends_data.csv', 'r', encoding='utf-8', newline='') as f:
                return list(csv.DictReader(f))
        except: return []

    def save_friends_data(self, data):
        """保存好友数据"""
        if not data: return
        with open('friends_data.csv', 'w', encoding='utf-8', newline='') as f:
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
        for d in data:
            if d['steamid'] not in current and d['is_friend'] == '✅':
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


class SteamFriendsApp:
    def __init__(self):
        self.steam_friends, self.settings_manager = SteamFriendsFixedGUI(), SettingsManager()
        self.settings, self.page = self.settings_manager.load_settings(), None

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
        def create_text_field(label, hint, value_key, password=False):
            return ft.TextField(
                label=label, hint_text=hint, password=password,
                value=self.settings.get(value_key, ''), width=300
            )

        self.api_key_input = create_text_field("Steam Web API Key", "输入你的Steam Web API密钥", 'api_key', True)
        self.steam_id_input = create_text_field("Steam ID", "输入你的Steam ID", 'steam_id')
        self.proxy_input = create_text_field("代理地址 (可选)", "http://127.0.0.1:7890", 'proxy')

        self.progress_bar = ft.ProgressBar(width=400, visible=False)
        self.status_text = ft.Text("就绪", size=14)
        self.sort_indicator = ft.Icon(ft.Icons.ARROW_UPWARD, size=16)
        
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("头像"), numeric=True),
                ft.DataColumn(ft.Text("昵称"), tooltip="好友昵称"),
                ft.DataColumn(ft.Text("Steam ID"), tooltip="Steam 64位ID"),
                ft.DataColumn(ft.Text("状态"), numeric=True, tooltip="好友状态"),
                ft.DataColumn(
                    ft.Row([ft.Text("成为好友时间"), self.sort_indicator], spacing=5),
                    tooltip="点击排序", on_sort=lambda e: self._toggle_sort()
                ),
                ft.DataColumn(ft.Text("删除时间"), tooltip="被删除的时间"),
                ft.DataColumn(ft.Text("备注"), tooltip="备注信息"),
            ],
            rows=[], expand=True, column_spacing=20,
            data_row_min_height=50, data_row_max_height=80
        )

        self.scroll_view = ft.Column([self.data_table], scroll=ft.ScrollMode.AUTO, 
                                   expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        button = lambda text, handler: ft.ElevatedButton(text=text, on_click=handler, width=150)
        self.update_button = button("更新好友列表", self.update_friends)
        self.delete_button = button("删除非好友记录", self.delete_non_friends)
        self.save_settings_button = button("保存设置", self.save_current_settings)
        self.refresh_avatar_button = button("刷新头像", self.refresh_avatars)
        self.refresh_avatar_button.visible = False

        # 创建帮助链接
        api_help = ft.TextButton("获取Steam API Key", on_click=lambda e: self.open_url("https://steamcommunity.com/dev/apikey"))
        steamid_help = ft.TextButton("查找Steam ID", on_click=lambda e: self.open_url("https://steamid.io/"))

        # 布局
        self.page.add(ft.Column([
            ft.Text("Steam好友管理工具", size=24, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Column([self.api_key_input, self.steam_id_input, self.proxy_input, ft.Row([api_help, steamid_help], spacing=10)], spacing=10),
                ft.Column([self.save_settings_button], alignment=ft.MainAxisAlignment.END)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([self.update_button, self.delete_button, self.refresh_avatar_button], 
                   alignment=ft.MainAxisAlignment.CENTER, spacing=20),
            ft.Row([self.status_text], alignment=ft.MainAxisAlignment.CENTER),
            self.progress_bar,
            ft.Container(self.scroll_view, expand=True, border=ft.border.all(1, ft.Colors.GREY_400), 
                        border_radius=10, padding=10, margin=ft.margin.symmetric(horizontal=10))
        ], expand=True, spacing=20, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

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
            avatar = ft.Container(
                content=ft.Image(src=item['avatar'], width=32, height=32, fit=ft.ImageFit.COVER, border_radius=16),
                width=32, height=32, border_radius=16, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor=ft.Colors.GREY_200
            )
            
            remark = ft.TextField(
                value=item['remark'] or '', width=180, height=30, dense=True,
                border=ft.InputBorder.NONE, filled=True, text_size=12, hint_text="添加备注...",
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREY_300),
                content_padding=ft.padding.only(left=8, right=8, top=5, bottom=5),
                on_change=lambda e, sid=item['steamid']: self._update_remark(sid, e.control.value)
            )
            
            self.data_table.rows.append(ft.DataRow([
                ft.DataCell(avatar),
                ft.DataCell(ft.Text(item['name'])),
                ft.DataCell(ft.Text(item['steamid'])),
                ft.DataCell(ft.Text(item['is_friend'])),
                ft.DataCell(ft.Text(item['bfd'])),
                ft.DataCell(ft.Text(item['removed_time'])),
                ft.DataCell(remark)
            ]))
        
        self.page.update()

    def update_friends(self, e):
        """更新好友列表"""
        if not all([self.api_key_input.value, self.steam_id_input.value]):
            self.status_text.value = "请填写API Key和Steam ID"
            return self.page.update()

        # 禁用按钮并显示进度
        for btn in [self.update_button, self.delete_button, self.refresh_avatar_button]:
            btn.disabled = True
        self.progress_bar.visible = True
        self.status_text.value = "正在更新好友列表..."
        self.page.update()

        def update_task():
            try:
                self.steam_friends.steam_web_api = self.api_key_input.value
                self.steam_friends.steam_id = self.steam_id_input.value
                self.steam_friends.set_proxy(self.proxy_input.value)
                data = self.steam_friends.update_friends_list()
                self.page.run_thread(lambda: self._finish_update(True, f"更新完成，共 {len(data)} 条记录"))
            except Exception as e:
                self.page.run_thread(lambda: self._finish_update(False, f"更新失败: {e}"))

        threading.Thread(target=update_task, daemon=True).start()

    def _finish_update(self, success, message):
        """完成更新后的UI处理"""
        for btn in [self.update_button, self.delete_button, self.refresh_avatar_button]:
            btn.disabled = False
        self.progress_bar.visible = False
        self.status_text.value = message
        if success:
            self._update_data_table()
            self.refresh_avatar_button.visible = True
        self.page.update()

    def delete_non_friends(self, e):
        """删除非好友记录"""
        # 禁用按钮并显示进度
        for btn in [self.update_button, self.delete_button, self.refresh_avatar_button]:
            btn.disabled = True
        self.progress_bar.visible = True
        self.status_text.value = "正在删除非好友记录..."
        self.page.update()

        def delete_task():
            try:
                data = self.steam_friends.delete_non_friends()
                self.page.run_thread(lambda: self._finish_delete(True, f"已删除非好友记录，剩余 {len(data)} 条记录"))
            except Exception as e:
                self.page.run_thread(lambda: self._finish_delete(False, f"删除失败: {e}"))

        threading.Thread(target=delete_task, daemon=True).start()

    def _finish_delete(self, success, message):
        """完成删除后的UI处理"""
        for btn in [self.update_button, self.delete_button, self.refresh_avatar_button]:
            btn.disabled = False
        self.progress_bar.visible = False
        self.status_text.value = message
        if success:
            self._update_data_table()
        self.page.update()

    def refresh_avatars(self, e):
        """刷新头像"""
        self.refresh_avatar_button.disabled = True
        self.progress_bar.visible, self.progress_bar.value = True, None
        self.status_text.value = "正在刷新头像..."
        self.page.update()
        
        def refresh_thread():
            try:
                data = self.steam_friends.read_friends_data()
                if not data:
                    return self.page.run_thread(lambda: self._finish_refresh(False, "没有数据需要刷新"))
                
                count = 0
                for item in data:
                    if item['steamid']:
                        url = f"https://avatars.akamai.steamstatic.com/{item['steamid']}_full.jpg"
                        new_path = self.steam_friends.download_avatar(url, item['steamid'])
                        if new_path != item['avatar']:
                            item['avatar'], count = new_path, count + 1
                
                if count:
                    self.steam_friends.save_friends_data(data)
                
                self.page.run_thread(lambda: self._finish_refresh(True, f"已刷新 {count} 个头像"))
            except Exception as e:
                self.page.run_thread(lambda: self._finish_refresh(False, f"刷新失败: {e}"))
        
        threading.Thread(target=refresh_thread, daemon=True).start()
    
    def _finish_refresh(self, success, message):
        """完成刷新后的UI处理"""
        self.refresh_avatar_button.disabled = False
        self.progress_bar.visible = False
        self.status_text.value = message
        if success: self._update_data_table()
        self.page.update()


if __name__ == '__main__':
    app = SteamFriendsApp()
    ft.app(target=app.main)