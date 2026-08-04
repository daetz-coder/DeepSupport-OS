---
title: "无法通过 HTTP 使用 MAPI 将成员添加到 Outlook 联系人组"
product: Outlook
category: Troubleshooting
source_url: https://support.microsoft.com/zh-CN/servicing/Exchange/troubleshooting/can-t-add-members-to-outlook-contact-group-by-using-mapi-over-http
language: zh-CN
fetched_at: 2026-08-04T11:47:06.540026+00:00
document_id: ms-071c73d8d64e
content_type: Troubleshooting
---

# 无法通过 HTTP 使用 MAPI 将成员添加到 Outlook 联系人组

> 来源: [https://support.microsoft.com/zh-CN/servicing/Exchange/troubleshooting/can-t-add-members-to-outlook-contact-group-by-using-mapi-over-http](https://support.microsoft.com/zh-CN/servicing/Exchange/troubleshooting/can-t-add-members-to-outlook-contact-group-by-using-mapi-over-http)

# 无法通过 HTTP 使用 MAPI 将成员添加到 Outlook 联系人组

应用对象
Exchange Server 2013 Enterprise Edition

## 症状

当用户尝试使用 MAPI over HTTP 配置文件将全局地址列表 (GAL) 的成员添加到 Outlook 中的联系人组时，联系人组列表中不会保存任何内容。

## 原因

该问题是由计算 Unicode 编码字符串长度时出错导致的。 此错误在解决联系人时触发异常，这会导致联系人保存操作失败。

## 解决方法

若要解决此问题，请安装以下累积更新：

3030080 2013 Exchange Server累积更新 8

## 状态

Microsoft 已确认在 "适用于" 部分中所列的 Microsoft 产品中存在问题。

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
