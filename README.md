# Steam好友管理工具 (Steam Friends Manager)

这是一个基于Python和Flet框架开发的Steam好友管理工具，用于追踪和管理您的Steam好友列表变化。该项目是从 [systemannounce/SteamFriends](https://github.com/systemannounce/SteamFriends) 项目改进而来的GUI版本。

## ✨ 功能特性

- **📊 好友列表追踪**: 自动记录Steam好友列表的变化，包括新增和删除的好友
- **🖼️ 头像缓存**: 自动下载并缓存好友头像到本地，提高加载速度
- **📈 状态监控**: 实时显示好友状态变化（✅ 当前好友 / ❌ 已删除好友）
- **📝 备注功能**: 为好友添加个性化备注
- **📋 CSV导出**: 将好友数据导出为CSV格式，便于备份和分析
- **🔍 代理支持**: 支持HTTP代理，解决网络访问限制
- **💾 自动保存**: 设置自动保存，窗口大小记忆
- **🎨 现代化UI**: 基于Flet的现代化图形界面

## 🚀 快速开始

### 环境要求

- Python 3.7 或更高版本
- Windows/macOS/Linux 操作系统

### 安装步骤

1. **克隆或下载项目**
   ```bash
   git clone https://github.com/your-username/steam-friends-gui.git
   cd steam-friends-gui
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **运行程序**
   ```bash
   python main.py
   ```

## 或者你可以选择去releases下载最新版本

## 🔧 配置说明

### 获取Steam API Key

1. 访问 [Steam Web API Key页面](https://steamcommunity.com/dev/apikey)
2. 登录您的Steam账号
3. 填写域名（可随意填写，如`localhost.com`）
4. 获取您的API Key

### 获取Steam ID

1. 访问 [SteamID查找网站](https://steamid.io/)
2. 输入您的Steam个人资料URL或自定义URL
3. 复制64位Steam ID（格式：76561198xxxxxxxxx）

### 代理配置（可选）

如果您的网络环境需要代理，请在设置中填写：
- HTTP代理格式：`http://127.0.0.1:7890`
- SOCKS代理格式：`socks5://127.0.0.1:1080`

## 📖 使用指南

### 首次使用

1. 启动程序后，在主界面输入您的Steam API Key和Steam ID
2. 点击"保存设置"按钮保存配置
3. 点击"更新好友列表"按钮获取初始好友列表

### 日常使用

- **更新好友列表**: 点击"更新好友列表"按钮，程序会自动检测好友变化
- **清理记录**: 点击"删除非好友记录"按钮，移除已删除好友的记录
- **刷新头像**: 如果头像显示异常，点击"刷新头像"按钮重新加载
- **添加备注**: 在CSV文件中为好友添加备注信息

### 数据文件

程序会自动创建以下文件：
- `steam_settings.json`: 存储程序设置
- `friends_data.csv`: 存储好友数据
- `avatar_cache/`: 头像缓存目录

## 📊 数据字段说明

| 字段名 | 说明 |
|--------|------|
| avatar | 好友头像路径 |
| name | 好友昵称 |
| steamid | Steam 64位ID |
| is_friend | 好友状态（✅当前好友 / ❌已删除） |
| bfd | 成为好友时间 |
| removed_time | 被删除时间 |
| remark | 备注信息 |

## 🛠️ 开发说明

### 项目结构

```
steam_friends_GUI/
├── main.py              # 主程序文件
├── steam_settings.json  # 配置文件示例
├── avatar_cache/        # 头像缓存目录
├── friends_data.csv     # 好友数据文件（自动生成）
├── LICENSE              # 许可证
└── README.md           # 说明文档
```

### 主要类说明

- **SettingsManager**: 管理程序设置和配置
- **SteamFriendsFixedGUI**: 核心功能类，处理Steam API交互
- **SteamFriendsApp**: GUI应用程序主类

### 技术栈

- **GUI框架**: [Flet](https://flet.dev/) - 基于Flutter的Python GUI框架
- **HTTP请求**: Requests库
- **数据处理**: JSON和CSV格式
- **异步处理**: Python线程池

## 🐛 常见问题

### Q: 程序无法获取好友列表？
**A**: 请检查以下几点：
- 确认Steam API Key有效且未过期
- 检查Steam隐私设置是否允许查看好友列表
- 确认Steam ID格式正确（64位数字）
- 检查网络连接和代理设置

### Q: 头像无法显示？
**A**: 尝试以下解决方案：
- 点击"刷新头像"按钮重新加载
- 检查avatar_cache目录权限
- 确认网络连接正常
- 删除avatar_cache目录后重新启动程序

### Q: 程序运行缓慢？
**A**: 优化建议：
- 首次运行会下载所有头像，请耐心等待
- 定期清理avatar_cache目录中不需要的头像
- 使用代理加速网络访问

## 🤝 贡献指南

欢迎提交Issue和Pull Request来帮助改进这个项目！

### 开发环境搭建

1. Fork本项目
2. 创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个Pull Request

## 📄 许可证

本项目基于MIT许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- 原始项目：[systemannounce/SteamFriends](https://github.com/systemannounce/SteamFriends)
- [Flet](https://flet.dev/) 提供优秀的Python GUI框架
- [Steam Web API](https://developer.valvesoftware.com/wiki/Steam_Web_API) 提供数据支持

## 📞 联系方式

如有问题或建议，欢迎通过以下方式联系：
- 提交 [GitHub Issue](https://github.com/your-username/steam-friends-gui/issues)

---

⭐ 如果这个项目对您有帮助，请给它一个Star！
