---
title: "每次退出时，系统都会提示你保存对 Normal.dotm 模板所做的更改Word"
product: Word
category: Guide
source_url: https://support.microsoft.com/zh-CN/Word/you-are-prompted-to-save-the-changes-to-the-normal-dotm-template-every-time-you-quit-word
language: zh-CN
fetched_at: 2026-08-04T11:50:06.455553+00:00
document_id: ms-410afdd69be7
content_type: Troubleshooting
---

# 每次退出时，系统都会提示你保存对 Normal.dotm 模板所做的更改Word

> 来源: [https://support.microsoft.com/zh-CN/Word/you-are-prompted-to-save-the-changes-to-the-normal-dotm-template-every-time-you-quit-word](https://support.microsoft.com/zh-CN/Word/you-are-prompted-to-save-the-changes-to-the-normal-dotm-template-every-time-you-quit-word)

# 每次退出时，系统都会提示你保存对 Normal.dotm 模板所做的更改Word

应用对象
Office Products

注意

这些步骤适用于 Microsoft 365 中的Word桌面版本或支持的永久版本。

## 摘要

退出Word时，系统可能会提示始终将更改保存到全局模板 Normal.dot。 或 Normal.dotm

可以关闭提示，Word将自动保存更改，但可能仍有问题。 因为 Normal.dot 或 Normal.dotm 模板可能感染了宏病毒。 若要解决此问题，可能需要更新病毒防护软件。

另一种可能性是，你可能有一个导致此问题的加载项。 若要解决此问题，可能需要确定导致该问题的加载项并将其从 Office 或Word启动文件夹中删除。

## 症状

每次退出Word时，都会收到以下消息：

进行了影响全局模板 Normal.dotm 的更改。 是否保存这些更改？

## 原因

出现此问题的原因可能如下。

### 原因 1：已安装的加载项或已安装的宏正在更改全局模板 Normal.dot 或 Normal.dotm

如果计算机上的加载项或宏修改了 Normal.dotm 模板，则可能会收到“症状”部分中列出的消息。 已知导致此行为的加载项包括：

- Stamps.com 互联网邮资
- 适用于 Microsoft Word 的 Works Suite 加载项

安装在 Word 中的加载项可能会将以下一项或多项添加到计算机：

- WLL 文件
- 模板
- COM 加载项
- 自动宏

#### 解决方法

启动Word时，Word会自动加载位于启动文件夹中的模板和加载项。 Word中的问题可能是由冲突或加载项问题导致的。 若要确定启动文件夹中的某个项是否导致该问题，请暂时清空该文件夹。

若要从启动文件夹中删除项目，请执行以下步骤：

- 退出Word的所有实例，Outlook (Outlook 使用 Word 作为其电子邮件编辑器) 。
- 在 Windows 桌面上，打开文件资源管理器并查找启动文件夹。 默认值为 C：\Users\<username>\AppData\Roaming\Microsoft\Word\STARTUP 提示 可以通过转到 “文件 选项 高级 ”，在“ 常规 ” >部分下选择“ 文件 >位置”，找到Word启动文件夹的确切路径。
- 将每个项目从启动文件夹拖动到桌面。 (或在桌面上创建一个文件夹，并将每个项目拖动到此新文件夹。) 注意 若要在桌面上创建新文件夹，请右键单击桌面上的空白区域，指向 “新建” ，然后单击“ 文件夹 ”。
- 启动 Word。 如果无法再重现该问题，并且从“启动”文件夹或文件夹中删除了多个项目，则可以尝试通过将文件逐个添加回相应的“启动”文件夹来隔离问题。 尝试在每次添加后重现问题，以确定导致该问题的文件。

如何删除 COM 加载项

COM 加载项可以安装在任何位置。 COM 加载项由与Word交互的程序安装。 若要查看已安装的 COM 加载项的列表，请执行以下步骤：

- 在“Word”中，转到 “文件 >选项 ”“加载项 ” >
- 在窗口底部，你将看到 “管理 COM 加载项 ”。选择它旁边的“ 转到 ”按钮。

如果“ COM 加载项”对话框中列出了加载项，请暂时关闭每个加载项。为此，请单击以清除列出的每个 COM 加载项的“检查”框，然后单击“ 确定 ”。 重启Word时，Word在未加载已关闭的 COM 加载项的情况下启动。

如果在关闭 COM 加载项后问题得到解决，列出的 COM 加载项之一就是问题的原因。 如果列出了多个 COM 加载项，可能需要确定哪个加载项导致了特定问题。 若要确定这一点，请一次重新打开一个 COM 加载项，然后重启Word。

如何删除Word自动宏

某些宏称为“自动”宏。 启动Word时，这些自动宏会自动运行。 下表列出了这些自动宏。 若要在不运行自动宏的情况下启动Microsoft Word，请在启动Word时按住 Ctrl 键，在安全模式下启动Word。

Macro
存储位置
自动运行
AutoExec
在普通模板或全局加载项中
开始Word
AutoNew
在模板中
创建基于模板的新文档时
AutoOpen
在文档或模板中
打开基于模板的文档或包含宏的文档时
自动关闭
在文档或模板中
关闭基于模板或包含宏的文档时
AutoExit
在普通模板或全局加载项中
退出Word

Word将名称以“Auto”开头的宏识别为宏，该宏在应用时自动运行。

如果在开始Word或在打开文档等Word执行操作时按住 SHIFT 键解决了问题，则自动宏就是问题所在。 若要解决此问题，请按照下列步骤操作：

- 在Word，转到应用顶部的 “搜索 ”框并键入Macros.
- 从显示的选项中选择“ 查看宏 ”。

在“ 宏 ”对话框中，可能会出现宏列表。 如果列出的任何宏以“Auto”开头，则可能需要删除此宏。 若要删除自动宏，请单击该宏，然后单击 删除 。

注意

宏可能已由Word加载项添加。 若要确定哪个模板包含宏，请将“ 宏” 框更改为列出的模板。 确定哪个模板包含宏后，可能需要从计算机中删除该模板。 删除Word加载项添加的模板可能会减少或停止加载项的功能。

### 原因 2：Word感染了宏病毒

如果计算机感染了更改全局模板的病毒，则可能会出现此问题。 若要帮助避免病毒感染，请使用最新版本更新防病毒软件和病毒定义。 请向防病毒软件供应商询问最新信息。

有关其他信息，请参阅 保护自己免受宏病毒的侵害。

### 如果你不想再看到消息...

如果选中了“ 保存普通模板前的提示 检查”框，则会收到此消息。

若要关闭此消息，请执行以下步骤。

重要

在 Word 中关闭此消息不会解决导致模板更改开始的任何问题，Word只是在保存它之前停止询问你。 可能仍必须执行本文中列出的其他步骤。

- 在Word转到 “文件 >选项 高级 ” >
- 在 “保存 组”下，取消选择 “保存普通”模板前的提示 。

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
