---
title: "OneDrive 无法启动"
product: OneDrive
category: Troubleshooting
source_url: https://support.microsoft.com/zh-CN/onedrive/onedrive-won-t-start
language: zh-CN
fetched_at: 2026-08-04T11:47:59.224354+00:00
document_id: ms-8acf42f06e24
content_type: Troubleshooting
---

# OneDrive 无法启动

> 来源: [https://support.microsoft.com/zh-CN/onedrive/onedrive-won-t-start](https://support.microsoft.com/zh-CN/onedrive/onedrive-won-t-start)

# OneDrive 无法启动

## OneDrive 无法启动的常见原因

安装 OneDrive 同步 应用 (onedrive.exe) 同步 OneDrive 的工作或学校文件或更新操作系统后，可能会遇到以下一个或多个症状：

- 系统不会提示你登录。
- 不会同步文件，并且不显示错误消息。
- 如果同时运行 OneDrive 个人版，并且单击“ 添加企业 帐户”对话框中的“ 设置” ，则不会发生任何操作。

## 成功启动 OneDrive 的故障排除步骤

组织的管理员已配置组策略设置，以防止 onedrive.exe 启动。 请与公司的管理员协作，更改适用的 组策略 对象 (GPO) 。 可以按照以下步骤确认计算机是否受策略影响。

重要

仔细按照本节中的步骤操作。 如果注册表修改错误，可能会出现严重问题。 修改之前， 备份注册表以便在发生问题时进行还原 。

- 导航到以下注册表项： HKEY_LOCAL_MACHINE\Software\Policies\Microsoft\Windows\OneDrive
- 检查以下项： DisableFileSyncNGSC = DWORD:1

若要与工作或学校的 OneDrive 同步，必须删除 DisableFileSyncNGSC 密钥，或者 必须将 DWORD 值更改为 0 (零) 。 如果注册表值设置为 组策略 对象的一部分，则必须删除该策略。

如果你决定手动更改此密钥或删除密钥而不让管理员更改计算机的策略，则下次运行策略时 (通常在重启后、登录到 Windows 或定期更新) 之后运行策略时，将重新应用该策略，并且 OneDrive for work 或 school 不会再次启动。

## 其他 OneDrive 启动故障排除资源

如果计算机上存在阻止 OneDrive for Work 或 School 启动的组策略设置，则会出现此问题。

如果公司的管理员决定禁用 OneDrive 的使用者同步应用，但要为工作或学校启用 OneDrive，请参阅 使用组策略控制OneDrive 同步应用设置 。

是否仍需要帮助？ 请转到 Microsoft 社区 。

## 需要更多帮助吗？

- 个人帐户
- 工作/学校帐户

帐户支持。 有关Microsoft帐户和订阅的帮助，请访问 帐户 & 计费帮助 。

技术支持。 对于技术支持，请选择下面的“ 联系Microsoft 支持部门 ”，输入问题并选择“ 获取帮助 ”。

联系人Microsoft 支持部门

移动用户可以通过打开 OneDrive 应用并轻轻摇动设备来联系支持人员。

社区支持。 社区可帮助你提问、提供反馈，并听取具有丰富知识的专家意见。 询问Microsoft社区 。 请勿在公共论坛中披露个人或敏感信息。

技术支持。 如需技术支持，请联系组织的 IT 支持人员、服务台或管理员。

IT 管理员。 IT 管理员应查看 OneDrive 管理员的帮助 、 OneDrive 技术社区 或联系 Microsoft 365 以获取业务支持 。

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
