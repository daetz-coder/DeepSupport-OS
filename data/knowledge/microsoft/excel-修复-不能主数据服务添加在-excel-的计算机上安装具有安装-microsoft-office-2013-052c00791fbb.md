---
title: "修复： 不能主数据服务添加在 excel 的计算机上安装具有安装 Microsoft Office 2013"
product: Excel
category: Troubleshooting
source_url: https://support.microsoft.com/zh-cn/topic/%E4%BF%AE%E5%A4%8D-%E4%B8%8D%E8%83%BD%E4%B8%BB%E6%95%B0%E6%8D%AE%E6%9C%8D%E5%8A%A1%E6%B7%BB%E5%8A%A0%E5%9C%A8-excel-%E7%9A%84%E8%AE%A1%E7%AE%97%E6%9C%BA%E4%B8%8A%E5%AE%89%E8%A3%85%E5%85%B7%E6%9C%89%E5%AE%89%E8%A3%85-microsoft-office-2013-0c9d74b5-cc64-d486-f2db-9edf35976fe8
language: zh-CN
fetched_at: 2026-08-04T11:49:59.201186+00:00
document_id: ms-052c00791fbb
content_type: Troubleshooting
---

# 修复： 不能主数据服务添加在 excel 的计算机上安装具有安装 Microsoft Office 2013

> 来源: [https://support.microsoft.com/zh-cn/topic/%E4%BF%AE%E5%A4%8D-%E4%B8%8D%E8%83%BD%E4%B8%BB%E6%95%B0%E6%8D%AE%E6%9C%8D%E5%8A%A1%E6%B7%BB%E5%8A%A0%E5%9C%A8-excel-%E7%9A%84%E8%AE%A1%E7%AE%97%E6%9C%BA%E4%B8%8A%E5%AE%89%E8%A3%85%E5%85%B7%E6%9C%89%E5%AE%89%E8%A3%85-microsoft-office-2013-0c9d74b5-cc64-d486-f2db-9edf35976fe8](https://support.microsoft.com/zh-cn/topic/%E4%BF%AE%E5%A4%8D-%E4%B8%8D%E8%83%BD%E4%B8%BB%E6%95%B0%E6%8D%AE%E6%9C%8D%E5%8A%A1%E6%B7%BB%E5%8A%A0%E5%9C%A8-excel-%E7%9A%84%E8%AE%A1%E7%AE%97%E6%9C%BA%E4%B8%8A%E5%AE%89%E8%A3%85%E5%85%B7%E6%9C%89%E5%AE%89%E8%A3%85-microsoft-office-2013-0c9d74b5-cc64-d486-f2db-9edf35976fe8)

应用对象
Excel

## 症状

当您尝试安装 Microsoft SQL Server 2012年主数据服务外接程序的 Microsoft Excel 运行 Microsoft Office 2013年的计算机上时，安装过程将失败。 此外，你还会收到以下错误消息：

未安装这些系统必备组件： 可以从安装 64 位版本的 Microsoft Excel 2010All 系统必备组件： http://go.microsoft.com/fwlink/?linkId=219530

注意

- 即使您的计算机上安装 Office 2013 旁边的 Microsoft Excel 2010，将出现此问题。
- 您可以安装主数据服务添加在 excel 卸载 Office 2013 之后。
- 如果安装 2007 Microsoft Office system 或而不是办公室 2013年的 Microsoft Office 2010年，就不会发生此问题。

## 解决方案

注意SQL Server 2012 Service Pack 1 版本的主数据服务外接的 Excel （或更高版本的功能包） 是所必需的外接程序以使用 Office 2013.You 可以下载 Microsoft SQL Server 2012 Service Pack 1 (SP1) 主数据服务加载项 Microsoft Excel 从 Microsoft 下载中心获取：

Microsoft SQL Server 2012 Service Pack 1 (SP1) 主数据服务加载项以 Microsoft Excel 选择匹配的现有 Excel 2013 安装 32 位或 64 位性质的下载。

- 对于 64 位 Excel，下载MasterDataServicesExcelAddin_amd64.msi。
- 对于 32 位 Excel，下载MasterDataServicesExcelAddin_x86.msi。

要确定安装了哪个版本的 Excel，请启动 Microsoft Excel，然后创建一个新工作簿。 单击文件，单击帐户选项卡，然后单击 关于 Excel 的版本信息，请参阅。

## 状态

Microsoft 已确认这是在“适用范围”部分中列出的 Microsoft 产品存在的问题。

## 更多信息

SQL Server 2012年服务包 1 主数据服务外接 excel 是使用 2007 Office 系统、 Office 2010 和 Office 2013 兼容。 它也是与主数据服务服务器安装的 SQL Server 2012年和 SQL Server 2012 Service Pack 1 版本兼容。

## 参考

有关主数据服务添加在 excel 的详细信息，请访问以下 MSDN 网站：

主数据服务加载项以 Microsoft Excel

[订阅 RSS 源](/zh-cn/rss-feed-picker)

### 需要更多帮助?

### 需要更多选项?

发现
社区

了解订阅权益、浏览培训课程、了解如何保护设备等。

Microsoft 365 订阅权益

Microsoft 365 培训

Microsoft 安全性

辅助功能中心

社区可帮助你提出和回答问题、提供反馈，并听取经验丰富专家的意见。

咨询 Microsoft 社区

Microsoft 技术社区

Windows 预览体验成员

Microsoft 365 预览体验

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
