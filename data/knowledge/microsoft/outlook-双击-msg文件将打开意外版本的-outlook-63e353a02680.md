---
title: "双击.msg文件将打开意外版本的 Outlook"
product: Outlook
category: Guide
source_url: https://support.microsoft.com/zh-CN/Outlook/double-clicking-a-msg-file-opens-an-unexpected-version-outlook
language: zh-CN
fetched_at: 2026-08-04T11:28:48.614179+00:00
document_id: ms-63e353a02680
content_type: Troubleshooting
---

# 双击.msg文件将打开意外版本的 Outlook

> 来源: [https://support.microsoft.com/zh-CN/Outlook/double-clicking-a-msg-file-opens-an-unexpected-version-outlook](https://support.microsoft.com/zh-CN/Outlook/double-clicking-a-msg-file-opens-an-unexpected-version-outlook)

# 双击.msg文件将打开意外版本的 Outlook

应用对象
Outlook 2016
Outlook 2013
Microsoft Outlook 2010

## 症状

如果双击.msg文件时Microsoft Outlook 2016或 Outlook 2013 未运行，则会打开早期版本的 Outlook。

## 原因

如果将 Outlook 2016 或 Outlook 2013 (作为即点即用安装的 Office) 与 Outlook 早期版本安装在同一台计算机上，则可能会出现此问题。 如果在早期版本的 Office 上执行软件更新或修复，则计算机上的文件关联可能会重置为该特定版本的 Office。 例如，以下注册表数据显示.msg文件扩展名与 Outlook 2010 相关联。

键：HKEY_CLASSES_ROOT\.msg 字符串： (默认) 值：Outlook.File.msg.14

## 解决方法

若要解决此问题，请按照以下步骤重置文件关联：

- 退出当前正在运行的任何 Outlook 版本。 Windows 10 右键单击扩展名为 .msg 的任何文件，指向 “打开使用” ，然后单击“ 选择另一个应用 ”。 在“ 如何打开此文件？” 对话框中，选择“ 其他选项” 部分下的 “Outlook (桌面) ”。 (下面列出了步骤 2 和步骤 3 的屏幕截图) 。 单击以启用 “始终使用此应用打开.msg文件 ”选项，然后单击“ 确定 ”。 Windows 8.1 或 Windows 8 右键单击扩展名为 .msg 的任何文件，然后单击“ 打开使用 ”。 在“ 如何打开此文件？” 对话框中，单击以启用“ 将此应用用于所有.msg文件 ”选项。 单击 “Outlook (桌面) ”。 Windows 7 右键单击扩展名为 .msg 的任何文件，指向 “打开”， 然后单击“ 选择默认程序 ”。 在“ 打开使用 ”对话框中，选择“ 始终使用所选程序”打开此类文件 。 然后，选择 “Outlook (桌面) ”，然后单击“ 确定 ”。

## 详细信息

有关 Office 的即点即用安装的详细信息，请访问以下Microsoft网站：

即点即用概述 大多数安装 Office 2016 或 Office 2013 的用户将使用即点即用安装 Office。 由于 Office 即点即用不会卸载任何以前的 Office 版本，因此你将在共存配置中使用 Office。 如果你不需要在计算机上安装早期版本的 Office，并且你只使用 Office 2016 或 Office 2013 程序，则应考虑卸载早期版本的 Office。

按照以下步骤卸载早期版本的 Office：

- 退出当前正在运行的任何 Office 程序。
- 启动 控制面板 。
- 单击“卸载程序” 。
- 在已安装的程序列表中选择早期版本的 Office 条目，然后单击“ 卸载 ”。
- 当系统提示确认要删除早期 Office 版本时，单击“ 是 ”。

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
