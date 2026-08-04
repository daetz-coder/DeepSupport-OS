---
title: "关于在 Office 中上传到 OneDrive 的体验，管理员需要了解什么"
product: OneDrive
category: Guide
source_url: https://support.microsoft.com/zh-CN/Office/collab-files/what-administrators-need-to-know-about-the-upload-to-onedrive-experience-in-office
language: zh-CN
fetched_at: 2026-08-04T11:47:41.487412+00:00
document_id: ms-b72213f23f42
content_type: Troubleshooting
---

# 关于在 Office 中上传到 OneDrive 的体验，管理员需要了解什么

> 来源: [https://support.microsoft.com/zh-CN/Office/collab-files/what-administrators-need-to-know-about-the-upload-to-onedrive-experience-in-office](https://support.microsoft.com/zh-CN/Office/collab-files/what-administrators-need-to-know-about-the-upload-to-onedrive-experience-in-office)

# 关于在 Office 中上传到 OneDrive 的体验，管理员需要了解什么

应用对象
Microsoft 365 专属 Excel
Microsoft 365 专属 Word
Microsoft 365 专属 PowerPoint

从 2020 年 11 月开始，我们将在 Word、Excel 和 PowerPoint for Windows 中推出两项新功能，旨在帮助用户将文件上传到 OneDrive。 第一个功能可防止上传到 OneDrive 的文档副本，而第二个功能可提供上传到 OneDrive 的提示，可帮助用户利用自动保存和实时协作等功能。 本文将回答管理员关于此新体验的一些常见问题。

## 在上传时移动文件

用户反馈当前上传到 OneDrive 的体验，会将文件的副本上传到 OneDrive，这会导致混乱，因为之后该文件的本地和 OneDrive 版本都可以打开。 现在，从非 OneDrive 位置上传到 OneDrive 时，将允许移动文件，这样默认情况下用户仅需管理文件的一个副本。 如果要保留两个副本，用户可以取消选中“上传后删除本地文件”复选框。

## 提示将文件上传到 OneDrive

当用户从电子邮件附件或其他只读源接收文件时，它们将暂时存储在本地。 在某些情况下，用户对这些文件进行编辑，系统可能会提示用户将文件上传到 OneDrive 以保存所做的更改。

## 如果我的组织或用户无法使用 OneDrive 会发生什么情况？

这些更改仅适用于用户将 OneDrive 帐户连接到 Word、Excel 或 PowerPoint 的情况。 如果用户未连接到 OneDrive 帐户，或现有策略在这些应用中禁用了 OneDrive，用户将不会看到这些功能。

## 新功能是否会覆盖组织设置的策略？

不会，现有管理员配置和组织策略仍将有效和实施。

## 用户是否可以更改这些行为？

不可以，但如果这些用户拒绝了上传提示，它在一段时间内不再会询问。

## 如果我的组织或用户将文件同步到 OneDrive 和其他同步服务，该怎么办？

将 Office 与 OneDrive 和第三方同步提供程序一起使用时，可能需要禁用这些功能。 我们提供了两个注册表项，第三方同步客户可将其设置为禁用。 如果你的组织使用第三方同步提供程序，则它们可能已实现了以下所述的更改，这将禁用其中的一项或两项功能。

禁用这些功能的两个注册表项位于 下 [HKEY_CURRENT_USER\SOFTWARE\Microsoft\Office\16.0\Common\FileIO] 。

- UploadToCloudDeleteOptionSuppressedTimeStamp - 此注册表项将删除“上传后删除本地文件”。 “上传” 对话框中的复选框。 所有通过此对话框完成的上传将作为副本执行，并且原始文件将保留在设备上。
- UploadToCloudPromptSuppressedTimeStamp - 此注册表项会阻止提示用户将文件上传到 OneDrive。 如果用户已登录并已连接到 OneDrive，用户仍可正常将文件上传到 OneDrive。

两个注册表项均为 QWORD，并且应指定一个时间值，采用 100 纳秒间隔，从 1601 年 1 月 1 日 (UTC) 开始。 有关详细信息，请参阅 FILETIME 结构。 应使用写入注册表键时的当前时间设置该值。 当任一注册表项的值处于过去的 30 天内时，相应功能将被禁用。

重要

表示未来日期或时间的时间戳将无法生效。

例如，下面的时间戳表示 2020 年 9 月 10 日晚上 11:23:30，在 2020 年 10 月10 日晚上 11:23:30 之前，在该日期和时间及之后评估时，将禁用提示：

UploadToCloudPromptSuppressedTimeStamp=hex(b): 80,5a,f5,f0,84,86,3f,b7

虽然单个组织可以设置这些密钥，但在这种情况下，应通过第三方文件同步服务定期将其设置为“心跳值”，防止组织运行混合环境时出现冲突、将文件同步到 OneDrive 和其他同步服务。 此处描述的详细信息可与第三方同步提供程序共享，以便禁用这些功能。

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
