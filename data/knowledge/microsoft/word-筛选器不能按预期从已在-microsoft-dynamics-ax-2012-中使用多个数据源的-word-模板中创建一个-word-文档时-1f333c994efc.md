---
title: "筛选器不能按预期从已在 Microsoft Dynamics AX 2012 中使用多个数据源的 Word 模板中创建一个 Word 文档时"
product: Word
category: Troubleshooting
source_url: https://support.microsoft.com/zh-cn/topic/%E7%AD%9B%E9%80%89%E5%99%A8%E4%B8%8D%E8%83%BD%E6%8C%89%E9%A2%84%E6%9C%9F%E4%BB%8E%E5%B7%B2%E5%9C%A8-microsoft-dynamics-ax-2012-%E4%B8%AD%E4%BD%BF%E7%94%A8%E5%A4%9A%E4%B8%AA%E6%95%B0%E6%8D%AE%E6%BA%90%E7%9A%84-word-%E6%A8%A1%E6%9D%BF%E4%B8%AD%E5%88%9B%E5%BB%BA%E4%B8%80%E4%B8%AA-word-%E6%96%87%E6%A1%A3%E6%97%B6-134d47d3-02cc-87ae-7cd3-399ea0ec79bf
language: zh-CN
fetched_at: 2026-08-04T11:50:21.694756+00:00
document_id: ms-1f333c994efc
content_type: Troubleshooting
---

# 筛选器不能按预期从已在 Microsoft Dynamics AX 2012 中使用多个数据源的 Word 模板中创建一个 Word 文档时

> 来源: [https://support.microsoft.com/zh-cn/topic/%E7%AD%9B%E9%80%89%E5%99%A8%E4%B8%8D%E8%83%BD%E6%8C%89%E9%A2%84%E6%9C%9F%E4%BB%8E%E5%B7%B2%E5%9C%A8-microsoft-dynamics-ax-2012-%E4%B8%AD%E4%BD%BF%E7%94%A8%E5%A4%9A%E4%B8%AA%E6%95%B0%E6%8D%AE%E6%BA%90%E7%9A%84-word-%E6%A8%A1%E6%9D%BF%E4%B8%AD%E5%88%9B%E5%BB%BA%E4%B8%80%E4%B8%AA-word-%E6%96%87%E6%A1%A3%E6%97%B6-134d47d3-02cc-87ae-7cd3-399ea0ec79bf](https://support.microsoft.com/zh-cn/topic/%E7%AD%9B%E9%80%89%E5%99%A8%E4%B8%8D%E8%83%BD%E6%8C%89%E9%A2%84%E6%9C%9F%E4%BB%8E%E5%B7%B2%E5%9C%A8-microsoft-dynamics-ax-2012-%E4%B8%AD%E4%BD%BF%E7%94%A8%E5%A4%9A%E4%B8%AA%E6%95%B0%E6%8D%AE%E6%BA%90%E7%9A%84-word-%E6%A8%A1%E6%9D%BF%E4%B8%AD%E5%88%9B%E5%BB%BA%E4%B8%80%E4%B8%AA-word-%E6%96%87%E6%A1%A3%E6%97%B6-134d47d3-02cc-87ae-7cd3-399ea0ec79bf)

本文适用于 AX 的所有地区。

## 症状

假定在 Microsoft Dynamics AX 2012 中使用 Word 外接程序。您可以在 Word 模板中使用多个数据源。例如，在 AX 中有两个查询来一些表。一个查询用于销售订单和订单行子表。其他查询用于销售订单表和费用交易记录的子表。在 Word 模板中包含两个表。第一个表将用于订单行和杂项费用交易记录使用第二个表。这种情况下，当从 Word 模板中创建一个 Word 文档筛选器将应用于第一个查询。但是，到第二个查询不适用于该筛选器。

## 解决方案

### 修补程序信息

可以从 Microsoft 获得受支持的修复程序。没有此知识库文章顶部"提供修补程序下载"部分。如果您遇到问题下载安装此修复程序，或有其他技术支持问题，请与您的合作伙伴或者，如果直接与 Microsoft 支持计划中进行注册，可以联系技术支持获取 Microsoft Dynamics 并创建一个新的支持请求。 为此，请访问下面的 Microsoft 网站︰

https://mbs.microsoft.com/support/newstart.aspx 您可以为 Microsoft Dynamics 按国家/地区特定的电话号码中使用这些链接的电话联系技术支持。 为此，请访问下面的 Microsoft 网站之一︰ 合作伙伴

https://mbs.microsoft.com/partnersource/support/ 客户

https://mbs.microsoft.com/customersource/support/information/SupportInformation/global_support_contacts_eng.htm 在特殊情况下，可免收的支持电话，可免收如果技术支持专业人员对 Microsoft Dynamics 和相关的产品的费用确定某个特定的更新能够解决您的问题。通常的支持费用将应用于任何其他支持问题和事项，不需要进行专门更新。

#### 安装信息

如果您有一个或多个方法或此修补程序不会影响表的自定义项时，您必须执行以下步骤︰

- 检查.xpo 文件中记录的更改。
- 应用此修复程序在生产环境中之前应用这些更改的测试环境中。

有关如何安装此修补程序的详细信息，请单击下面的文章编号，以查看 Microsoft 知识库中相应的文章︰

893082 如何安装 AX 修补程序

#### 系统必备组件

您必须具有要应用此修补程序的安装 Microsoft Dynamics AX 2012。

#### 重启要求

应用此修复程序后，必须重新启动应用程序对象服务器 (AOS) 服务。

#### 文件信息

此修补程序的全球版本具有的文件属性 （或更新的文件属性） 在下表中列出。日期和为这些文件的时间以协调世界时 (UTC) 列出。当您查看文件信息时，它将转换为本地时间。要了解 UTC 与本地时间之间的时差，请使用控制面板中的 日期和时间 项中的 时区 选项卡。

文件名称

文件版本

文件大小

日期

时间

平台

Aximpactanalysis.exe

不适用

60,280

14-Dec-2011

17:56

x86

Axupdate.exe

不适用

60,264

14-Dec-2011

17:56

x86

Clientoba32.msp

不适用

15,257,600

17-Jan-2012

06:17

不适用

Clientoba64.msp

不适用

15,257,600

17-Jan-2012

06:17

不适用

Components32.msp

不适用

13,459,456

17-Jan-2012

06:17

不适用

Components64.msp

不适用

27,062,272

17-Jan-2012

06:17

不适用

Helpserver64.msp

不适用

774,144

17-Jan-2012

06:17

不适用

Objectserver32.msp

不适用

5,283,840

17-Jan-2012

06:17

不适用

Objectserver64.msp

不适用

6,823,936

17-Jan-2012

06:17

不适用

Setupsupport32.msp

不适用

7,495,680

17-Jan-2012

06:17

不适用

Setupsupport64.msp

不适用

13,279,232

17-Jan-2012

06:16

不适用

Traceparser.msp

不适用

249,856

17-Jan-2012

06:17

不适用

Axsetupsp.exe

6.0.947.853

1,361,768

15-Jan-2012

11:13

x86

Axutillib.dll

6.0.947.0

817,512

14-Dec-2011

17:56

x86

Microsoft.dynamics.servicing.operations.dll

6.0.888.436

35,752

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

382,848

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

370,560

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

374,656

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

374,656

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

370,560

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

378,752

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

370,560

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

374,656

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

370,560

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

374,656

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

370,560

14-Dec-2011

17:56

x86

Axsetupsp.resources.dll

6.0.947.491

407,424

14-Dec-2011

17:56

x86

## 状态

Microsoft 已经确认这是“适用于”一节中列出的 Microsoft 产品中的问题。

注意：这是直接从创建 Microsoft 支持部门内的"快速发布"的文章。此处包含的信息是作为为了响应新出现的问题而提供的。由于以使其可用的速度，而材料可能包含印刷错误，恕不另行通知，随时可能进行修订。其他考虑因素，请参阅 使用条款 。

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
