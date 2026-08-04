---
title: "Outlook 电子邮件停滞"
product: Outlook
category: Sync
source_url: https://support.microsoft.com/zh-CN/Outlook/outlook-email-stuck
language: zh-CN
fetched_at: 2026-08-04T11:28:46.004386+00:00
document_id: ms-19b9dbfd645b
content_type: Troubleshooting
---

# Outlook 电子邮件停滞

> 来源: [https://support.microsoft.com/zh-CN/Outlook/outlook-email-stuck](https://support.microsoft.com/zh-CN/Outlook/outlook-email-stuck)

# Outlook 电子邮件停滞

应用对象
Microsoft Outlook 2010
Outlook 2013
Outlook.com

若要释放滞留在“草稿”或“发件箱”文件夹中的电子邮件，请选择以下部分之一。

## Email停滞在 Outlook 中

### 修复滞留在发件箱中的邮件

当邮件滞留在发件箱中时，最可能的原因是附件较大。

- 单击“ 脱机发送/接收 > 工作 ”。
- 在导航窗格中，单击“ 发件箱 ”。
- 在此处，您可以： 删除邮件。 只需将其选中，然后按 Delete。 将邮件拖动到草稿文件夹，双击可打开邮件，删除附件（单击它并按 Delete）。
- 如果显示错误消息，指出 Outlook 正在尝试传输邮件，请关闭 Outlook。 它可能需要花一些时间才会退出。 提示 如果 Outlook 不关闭，请按 Ctrl+Alt+Delete，然后单击“ 启动任务管理器 ”。 在“ 任务管理器中 ”中，单击“ 进程 ”选项卡，向下滚动到“ outlook.exe ”，然后单击“ 结束进程 ”。
- 关闭 Outlook 后，再次启动它，然后重复步骤 2 至 3。
- 删除附件后，单击“ 脱机发送/接收 > 工作” 以取消选择该按钮并恢复联机工作 。 提示 单击“ 发送 ”但未连接时，邮件也会卡在发件箱中。 单击“ 发送/接收 ”，然后查看“ 脱机工作 ”按钮。 如果是蓝色，则表示断开连接。 单击它进行连接（按钮变为白色），然后单击“ 全部发送 ”。

### Email不自动发送

症状

在 Microsoft Outlook 中发送电子邮件时，邮件可能保留在发件箱文件夹中，如下图所示。

出现此问题时，邮件将滞留在发件箱文件夹中，直到手动启动发送/接收操作 (例如，按 F9 或选择发送或接收) 。

原因

如果未启用“连接后立即发送”选项，则可能会出现此问题，如下图所示，Outlook 2016。

此设置与以下注册表数据关联，因此管理员还可通过修改注册表来配置此设置。

解决方案

使用以下步骤重新启用"连接后立即发送"选项。

- Outlook 2010 和更高版本 在“ 文件 ”选项卡上，选择“ 选项 ”。 在“Outlook 选项” 对话框中，选择“高级” 。 在“发送和接收”部分中，启用 “连接后立即发送 ”。 选择“ 确定 ”。
- Outlook 2007 和 Outlook 2003 在“ 工具 ”菜单上，选择“选项”。 在“选项” 对话框中，选择“邮件设置” 选项卡。 在"发送/接收" 部分，启用"连接后立即发送" 。 选择“ 确定 ”。

注意

如果由于灰显而无法重新启用此设置，则组策略将管理该设置。 在这种情况下，请与管理员联系以删除此组策略。

### Outlook 在加载配置文件时停滞不前

问题

更新到 当前频道版本 1905（内部版本 11629.20196） 及更高版本后，Outlook 可能会在加载配置文件时挂起或无法启动。 你可能会注意到，如果打开任务管理器，即使你没有打开应用程序，系统也会意外地列出其他 Office 进程。 如果你结束这些进程，则 Outlook 可以正常打开。

状态：已修复

2019 年 6 月 25 日，Outlook 团队对服务进行了更改以解决此问题。 如果此问题仍然存在，请重启几次 Outlook，以便其完成服务更改。

变通方法

若要解决此问题，你需要结束正在运行的所有 Office 进程并禁用状态功能。

在任务管理器中终止进程

- 右键单击任务栏上的任意位置，然后选择“ 任务管理器 ”。
- 在“ 进程 ”选项卡下，找到所有 Office 进程。
- 选择某个 Office 进程，然后选择“ 结束任务 ”。 对列出的每个 Office 进程重复此步骤。

禁用 Outlook 状态功能

- 在 Outlook 中，依次选择“ 文件 > ”、“选项”、“ > People
- 如果启用了以下选项，请取消选中这些选项的复选框： 在姓名旁边显示联机状态 可用时显示用户照片
- 选择“ 确定” ，然后重启 Outlook。

注意

禁用状态功能将有助于缓解此问题。 但是，如果你单击 Office 应用右上角的帐户图片或转到“文件”|“帐户”，则会话将打开，并再次触发此问题。

### Outlook 处于脱机状态

症状

使用 Microsoft Outlook 发送电子邮件时，不会立即发送邮件。 而是保留在发件箱文件夹中。 在安全模式下启动 Outlook 时不会发生此问题。

原因

当以下两项都为 true 时，会出现此问题：

- Exchange 电子邮件帐户配置为使用缓存 Exchange 模式。
- Windows 注册表中配置了以下数据： Outlook 2013、Outlook 2010 或 Outlook 2007 键：HKEY_CURRENT_USER\Software\Microsoft\Office\ x.0 \Outlook\Preferences DWORD：LoadTransportProviders 值：1 注意 在此注册表子项中， x.0 对应于您的 Outlook 版本 (15.0 = Outlook 2013,14.0 = Outlook 2010,12.0 = Outlook 2007)

解决方法

若要解决此问题，请对Microsoft Exchange Server邮箱使用联机模式配置文件。

注意

此方法是一个临时修复。 有关永久修复，请参阅“解决方法”部分。

解决方案

警告 如果使用注册表编辑器或其他方法错误地修改注册表，则可能会出现严重问题。 这些问题可能需要你重新安装操作系统。 Microsoft 无法保证可以解决这些问题。 修改注册表的风险由您自行承担。

若要解决此问题，请删除注册表中 LoadTransportProviders 的值。 请按以下步骤完成此操作：

- 启动注册表编辑器。
- 找到并选择以下注册表子项： <HKEY_CURRENT_USER\Software\Microsoft\Office\x.0>\Outlook\Preferences 注意 在此子项中， x.0 对应于您的 Outlook 版本 (15.0 = Outlook 2013,14.0 = Outlook 2010,12.0 = Outlook 2007) 。
- 右键单击“LoadTransportProvidersDWORD”值，然后单击“ 删除 ”。
- 退出注册表编辑器。

## Email卡在 Outlook.com

### 电子邮件未从 Outlook.com 发送

如果电子邮件不是从 Outlook.com 发送，请首先检查以下事项：

- 检查卡住的电子邮件是否位于 “草稿” 或 “发件箱” 文件夹中。
- 如果该邮件包含大于 25MB 的附件，请删除附件，附加较小的文件，或将文件上传到 OneDrive，然后在附件中附加一个链接。 接下来便可尝试再次发送此邮件。
- 如果 收件箱 已满，将无法发送或接收新邮件。 若要在收件箱中留出空间，请尝试通过右键单击“ 垃圾邮件Email 然后选择”空“文件夹来清 空垃圾邮件文件夹 。
- 如果使用电脑版或 Mac 版 Outlook 发送 Outlook.com 帐户电子邮件，请转到 “发送/接收 > 发送/接收所有文件夹 ”。

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
