import flet as ft
import requests
import json
import re
import csv
from datetime import datetime
import os
import threading
import json as jsonlib


class SettingsManager:
    def __init__(self):
        self.settings_file = 'steam_settings.json'
        self.default_settings = {
            'api_key': '',
            'steam_id': '',
            'proxy': '',
            'window_width': 900,
            'window_height': 700
        }
    
    def load_settings(self):
        """加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = jsonlib.load(f)
                    # 合并默认设置
                    merged = self.default_settings.copy()
                    merged.update(settings)
                    return merged
        except Exception:
            pass
        return self.default_settings.copy()
    
    def save_settings(self, settings):
        """保存设置"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                jsonlib.dump(settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False


class SteamFriendsFixedGUI:
    def __init__(self):
        self.steam_web_api = None
        self.steam_id = None
        self.friends = 0
        self.friend_ids = []
        self.friends_list = {}
        self.friend_data = []
        
        self.friend_list_url = 'https://api.steampowered.com/ISteamUser/GetFriendList/v0001/'
        self.friend_summaries_url = 'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/'
        self.sess = requests.Session()
        self.sess.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
        })
        
        # 创建头像缓存目录
        self.avatar_cache_dir = 'avatar_cache'
        if not os.path.exists(self.avatar_cache_dir):
            os.makedirs(self.avatar_cache_dir)

    def set_proxy(self, proxy):
        if proxy:
            self.sess.proxies.update({
                'http': proxy,
                'https': proxy,
            })

    def get_friend_list(self):
        params = {
            'key': self.steam_web_api,
            'steamid': self.steam_id,
        }
        response = self.sess.get(self.friend_list_url, params=params)
        
        if response.status_code == 200:
            json_list = json.loads(response.text)
            self.friends_list = {friend['steamid']: friend['friend_since'] for friend in json_list['friendslist']['friends']}
            self.friends = len(self.friends_list)
            return True
        elif response.status_code == 401:
            raise Exception("Unauthorized，请检查你的steam隐私设置")
        elif response.status_code == 403:
            raise Exception("403 Forbidden，请检查你的web_api和id的值")
        elif response.status_code == 500:
            raise Exception("服务器内部错误，请检查你的steamid的值")
        else:
            raise Exception(f"收到未处理的状态码：{response.status_code}")

    def get_friends_summaries(self):
        steam_ids = list(self.friends_list.keys())
        batch_size = 100
        
        for i in range(0, len(steam_ids), batch_size):
            batch = steam_ids[i:i+batch_size]
            steam_ids_str = ','.join(batch)
            
            params = {
                'key': self.steam_web_api,
                'steamids': steam_ids_str,
            }
            response = self.sess.get(self.friend_summaries_url, params=params)
            
            if response.status_code == 200:
                json_list = json.loads(response.text)
                users_list = json_list['response']['players']
                
                for user in users_list:
                    steamid = user['steamid']
                    name = re.sub(r'[|\-+:"\'\n\r]', '`', user['personaname'])
                    avatar_url = user['avatar']
                    
                    # 下载头像到本地缓存
                    local_avatar = self.download_avatar(avatar_url, steamid)
                    
                    bfd_unix = self.friends_list[steamid]
                    bfd = datetime.utcfromtimestamp(bfd_unix).strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.friend_data.append({
                        'avatar': local_avatar,  # 使用本地缓存路径
                        'name': name,
                        'steamid': steamid,
                        'is_friend': '✅',
                        'bfd': bfd,
                        'removed_time': '',
                        'remark': ''
                    })
            elif response.status_code == 429:
                raise Exception("429 Too Many Requests, 可能是web_api被ban")
            else:
                raise Exception(response.text)

    def read_friends_data(self):
        """读取现有的好友数据"""
        data = []
        try:
            if os.path.exists('./friends_data.csv'):
                with open('./friends_data.csv', 'r', encoding='utf-8', newline='') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        data.append(dict(row))
        except Exception:
            pass
        return data

    def save_friends_data(self, data):
        """保存好友数据到CSV文件"""
        if not data:
            return
            
        fieldnames = ['avatar', 'name', 'steamid', 'is_friend', 'bfd', 'removed_time', 'remark']
        with open('./friends_data.csv', 'w', encoding='utf-8', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    def download_avatar(self, avatar_url, steamid):
        """下载头像到本地缓存"""
        try:
            # 从URL中提取文件名
            filename = f"{steamid}_{os.path.basename(avatar_url)}"
            filepath = os.path.join(self.avatar_cache_dir, filename)
            
            # 如果文件已存在，直接返回本地路径
            if os.path.exists(filepath):
                return filepath
            
            # 下载头像
            response = self.sess.get(avatar_url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                return filepath
            
        except Exception as e:
            print(f"下载头像失败 {avatar_url}: {e}")
        
        return avatar_url  # 如果下载失败，返回原始URL

    def update_friends_list(self):
        """更新好友列表"""
        self.get_friend_list()
        self.get_friends_summaries()
        
        existing_data = self.read_friends_data()
        existing_dict = {item['steamid']: item for item in existing_data}
        
        current_steamids = set()
        for friend in self.friend_data:
            steamid = friend['steamid']
            current_steamids.add(steamid)
            
            if steamid in existing_dict:
                existing_dict[steamid].update({
                    'avatar': friend['avatar'],
                    'name': friend['name'],
                    'is_friend': '✅',
                    'removed_time': ''
                })
            else:
                existing_data.append(friend)
        
        for item in existing_data:
            if item['steamid'] not in current_steamids and item['is_friend'] == '✅':
                item['is_friend'] = '❌'
                if not item['removed_time']:
                    item['removed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.save_friends_data(existing_data)
        return existing_data

    def delete_non_friends(self):
        """删除非好友记录"""
        data = self.read_friends_data()
        filtered_data = [item for item in data if item['is_friend'] == '✅']
        self.save_friends_data(filtered_data)
        return filtered_data


class SteamFriendsApp:
    def __init__(self):
        self.steam_friends = SteamFriendsFixedGUI()
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_settings()
        self.page = None

    def main(self, page: ft.Page):
        self.page = page
        page.title = "Steam好友管理工具"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.window_width = self.settings.get('window_width', 900)
        page.window_height = self.settings.get('window_height', 700)
        page.window_resizable = True

        # 创建UI组件
        self.api_key_input = ft.TextField(
            label="Steam Web API Key",
            hint_text="输入你的Steam Web API密钥",
            value=self.settings.get('api_key', ''),
            password=True,
            width=300
        )
        
        self.steam_id_input = ft.TextField(
            label="Steam ID",
            hint_text="输入你的Steam ID",
            value=self.settings.get('steam_id', ''),
            width=300
        )
        
        self.proxy_input = ft.TextField(
            label="代理地址 (可选)",
            hint_text="http://127.0.0.1:7890",
            value=self.settings.get('proxy', ''),
            width=300
        )

        # 创建帮助链接
        api_help_link = ft.TextButton(
            text="获取Steam API Key",
            on_click=lambda e: self.open_url("https://steamcommunity.com/dev/apikey")
        )
        
        steamid_help_link = ft.TextButton(
            text="查找Steam ID",
            on_click=lambda e: self.open_url("https://steamid.io/")
        )

        self.progress_bar = ft.ProgressBar(width=400, visible=False)
        self.status_text = ft.Text("就绪", size=14)

        # 创建数据表格
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("头像")),
                ft.DataColumn(ft.Text("昵称")),
                ft.DataColumn(ft.Text("Steam ID")),
                ft.DataColumn(ft.Text("状态")),
                ft.DataColumn(ft.Text("成为好友时间")),
                ft.DataColumn(ft.Text("删除时间")),
                ft.DataColumn(ft.Text("备注")),
            ],
            rows=[],
            expand=True
        )

        # 创建滚动视图
        self.scroll_view = ft.Column(
            [self.data_table],
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        # 创建按钮
        self.update_button = ft.ElevatedButton(
            text="更新好友列表",
            on_click=self.update_friends,
            width=150
        )
        
        self.delete_button = ft.ElevatedButton(
            text="删除非好友记录",
            on_click=self.delete_non_friends,
            width=150
        )
        
        self.save_settings_button = ft.ElevatedButton(
            text="保存设置",
            on_click=self.save_current_settings,
            width=150
        )
        
        self.refresh_avatar_button = ft.ElevatedButton(
            text="刷新头像",
            on_click=self.refresh_avatars,
            width=150,
            visible=False  # 初始隐藏
        )

        # 布局
        page.add(
            ft.Column([
                ft.Text("Steam好友管理工具", size=24, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Column([
                        self.api_key_input,
                        self.steam_id_input,
                        self.proxy_input,
                        ft.Row([
                            api_help_link,
                            steamid_help_link
                        ], spacing=10)
                    ], spacing=10),
                    ft.Column([
                        self.save_settings_button
                    ], alignment=ft.MainAxisAlignment.END)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    self.update_button,
                    self.delete_button,
                    self.refresh_avatar_button
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                ft.Row([self.status_text], alignment=ft.MainAxisAlignment.CENTER),
                self.progress_bar,
                ft.Container(
                    self.scroll_view,
                    expand=True,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=10,
                    padding=10
                )
            ], expand=True, spacing=20)
        )

        # 保存窗口大小变化
        def on_window_resize(e):
            self.settings['window_width'] = page.window_width
            self.settings['window_height'] = page.window_height
        
        page.on_resize = on_window_resize

        # 加载现有数据
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
        
        if self.settings_manager.save_settings(settings):
            self.status_text.value = "设置已保存"
            self.page.update()
        else:
            self.status_text.value = "保存设置失败"
            self.page.update()

    def load_existing_data(self):
        try:
            data = self.steam_friends.read_friends_data()
            if data:
                self.update_table(data)
                self.status_text.value = f"已加载 {len(data)} 条记录"
                self.refresh_avatar_button.visible = True  # 显示刷新头像按钮
                self.page.update()
            else:
                self.status_text.value = "暂无数据，请先更新好友列表"
                self.refresh_avatar_button.visible = False
                self.page.update()
        except Exception as e:
            self.status_text.value = f"加载数据失败: {str(e)}"
            self.refresh_avatar_button.visible = False
            self.page.update()

    def update_table(self, data):
        self.data_table.rows.clear()
        
        for item in data:
            # 确保头像URL使用HTTPS协议
            avatar_url = item['avatar']
            if avatar_url.startswith('http://'):
                avatar_url = avatar_url.replace('http://', 'https://')
            
            # 创建头像显示组件，使用更可靠的配置
            avatar_img = ft.Image(
                src=avatar_url,
                width=32,
                height=32,
                fit=ft.ImageFit.COVER,
                border_radius=16,
                gapless_playback=True,
                repeat=ft.ImageRepeat.NO_REPEAT,
            )
            
            # 创建头像容器，使用ClipOval实现圆形头像
            avatar_container = ft.Container(
                content=avatar_img,
                width=32,
                height=32,
                border_radius=16,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor=ft.Colors.GREY_200,
                padding=0,
                margin=0,
            )
            
            self.data_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(avatar_container),
                        ft.DataCell(ft.Text(item['name'])),
                        ft.DataCell(ft.Text(item['steamid'])),
                        ft.DataCell(ft.Text(item['is_friend'])),
                        ft.DataCell(ft.Text(item['bfd'])),
                        ft.DataCell(ft.Text(item['removed_time'])),
                        ft.DataCell(ft.Text(item['remark'])),
                    ]
                )
            )
        
        self.page.update()

    def update_friends(self, e):
        if not self.api_key_input.value or not self.steam_id_input.value:
            self.status_text.value = "请填写API Key和Steam ID"
            self.page.update()
            return

        self.progress_bar.visible = True
        self.status_text.value = "正在更新好友列表..."
        self.page.update()

        def update_task():
            try:
                self.steam_friends.steam_web_api = self.api_key_input.value
                self.steam_friends.steam_id = self.steam_id_input.value
                self.steam_friends.set_proxy(self.proxy_input.value)
                
                data = self.steam_friends.update_friends_list()
                
                self.status_text.value = f"更新完成，共 {len(data)} 条记录"
                self.update_table(data)
                self.refresh_avatar_button.visible = True
                
            except Exception as e:
                self.status_text.value = f"更新失败: {str(e)}"
            finally:
                self.progress_bar.visible = False
                self.page.update()

        thread = threading.Thread(target=update_task)
        thread.start()

    def delete_non_friends(self, e):
        self.progress_bar.visible = True
        self.status_text.value = "正在删除非好友记录..."
        self.page.update()

        def delete_task():
            try:
                data = self.steam_friends.delete_non_friends()
                self.status_text.value = f"已删除非好友记录，剩余 {len(data)} 条记录"
                self.update_table(data)
            except Exception as e:
                self.status_text.value = f"删除失败: {str(e)}"
            finally:
                self.progress_bar.visible = False
                self.page.update()

        thread = threading.Thread(target=delete_task)
        thread.start()

    def refresh_avatars(self, e):
        """刷新所有头像显示"""
        self.status_text.value = "正在刷新头像..."
        self.page.update()
        
        # 重新加载数据以刷新头像
        data = self.steam_friends.read_friends_data()
        if data:
            self.update_table(data)
            self.status_text.value = f"已刷新 {len(data)} 个头像"
        else:
            self.status_text.value = "无数据可刷新"
        
        self.page.update()


if __name__ == '__main__':
    app = SteamFriendsApp()
    ft.app(target=app.main)