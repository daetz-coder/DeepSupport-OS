---
title: "安装 2017 年 10 月Microsoft Outlook 安全更新后，Outlook Microsoft Dynamics 365无法呈现网页"
product: Outlook
category: Troubleshooting
source_url: https://support.microsoft.com/zh-CN/servicing/dynamics/crm/troubleshooting/microsoft-dynamics-365-for-outlook-is-unable-to-render-webpages-after-installing-the-october-2017-mi
language: zh-CN
fetched_at: 2026-08-04T11:47:02.674038+00:00
document_id: ms-bc1571572c04
content_type: Troubleshooting
---

# 安装 2017 年 10 月Microsoft Outlook 安全更新后，Outlook Microsoft Dynamics 365无法呈现网页

> 来源: [https://support.microsoft.com/zh-CN/servicing/dynamics/crm/troubleshooting/microsoft-dynamics-365-for-outlook-is-unable-to-render-webpages-after-installing-the-october-2017-mi](https://support.microsoft.com/zh-CN/servicing/dynamics/crm/troubleshooting/microsoft-dynamics-365-for-outlook-is-unable-to-render-webpages-after-installing-the-october-2017-mi)

# 安装 2017 年 10 月Microsoft Outlook 安全更新后，Outlook Microsoft Dynamics 365无法呈现网页

应用对象
Dynamics CRM
Outlook 2016
Outlook 2013
Outlook for Microsoft 365
Microsoft Outlook 2010
Microsoft CRM client for Microsoft Office Outlook
Microsoft Dynamics CRM 2011
Dynamics CRM 2013
Microsoft Dynamics CRM 2013 Service Pack 1
Dynamics CRM Online
Dynamics CRM 2015
Dynamics CRM 2016
Microsoft Dynamics CRM 2016 Service Pack 1
December 2016 Service Pack for Dynamics 365 (CRM 2016)

## 症状

尝试使用Microsoft Outlook 外接程序 (Outlook 客户端) Microsoft Dynamics 365通过 Outlook 文件夹窗格呈现网页时，视图窗格将保持空白，并且“正在等待从 CRM 服务器检索页面...”。显示。 窗格永远不会加载相应的网页。

## 原因

Outlook 加载项Dynamics 365依赖于自定义漫游主页，以便在 Outlook 中呈现网页。 2017 年 10 月Microsoft Outlook 安全更新禁用 Outlook 中的漫游主页以解决应用程序的重大漏洞，因此，无意中导致加载项失败。

有关此问题发生原因的详细信息，请参阅 Outlook 中的以下文章：

文件夹属性中缺少 Outlook 主页功能

## 版本控制信息

Microsoft Outlook 外接程序系列的所有Microsoft Dynamics 365版本都受此问题影响。 这包括 Microsoft Dynamics CRM 2016 for Microsoft Office Outlook、Microsoft Dynamics CRM 2015 for Microsoft Office Outlook 和 Microsoft Dynamics CRM 2013 for Microsoft Office Outlook。

这也会影响加载项连接到的所有Dynamics 365/CRM 组织版本。

Outlook 安全更新版本控制信息如下：

Microsoft Outlook 2010 (KB4011089) 32 位版安全更新 Microsoft Outlook 2010 (KB4011089) 64 位版本的安全更新 Microsoft Outlook 2010 (KB4011196) 32 位版安全更新 Microsoft Outlook 2010 (KB4011196) 64 位版本的安全更新 Microsoft Outlook 2013 (KB4011178) 32 位版安全更新 Microsoft Outlook 2013 (KB4011178) 64 位版本的安全更新 Microsoft Outlook 2016 (KB4011162) 32 位版安全更新 Microsoft Outlook 2016 (KB4011162) 64 位版安全更新

任何将来的累积 Outlook 更新都将包含这些安全汇报，并将导致此问题发生，例如以下更新：

Microsoft Outlook 2013 (KB4011252) 32 位版的更新 Microsoft Outlook 2013 (KB4011252) 64 位版本的更新 Microsoft Outlook 2016 (KB4011240) 32 位版的更新 Microsoft Outlook 2016 (KB4011240) 64 位版的更新

## 解决方法

对于 Office Outlook 的即点即用安装，此问题已在 2018 年 3 月初发布的每月频道中得到解决。 确保拥有 Office Outlook 的最新更新：

如何安装适用于 Microsoft Outlook 的最新适用更新

对于 Office Outlook 的 MSI 安装，此问题在 2018 年 8 月 14 日Microsoft Office Outlook 2010、2013 和 2016 安全更新中得到解决：

Outlook 2010 安全更新：2018 年 8 月 14 日KB4032222 Outlook 2013 安全更新：2018 年 8 月 14 日 KB4032240 Outlook 2016 安全更新：2018 年 8 月 14 日KB4032235

安装与 Office Outlook 的 MSI 版本匹配的上述更新将导致页面正确显示。

## 详细信息

此问题的症状与 2018 年 8 月 Office 预览体验成员更新导致的即点即用 Office 安装出现的问题类似。 有关此问题的详细信息，请参阅以下位置：

安装 2018 年 8 月 Office 预览体验成员更新后，outlook Microsoft Dynamics 365无法呈现网页

有关此安全更新的详细信息，请参阅以下链接：

Microsoft Outlook 安全汇报列表 Microsoft有关此问题的 Outlook 文档

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
