---
title: "安装 2024 年 4 月 9 日更新后，可能会禁用 PowerPoint 2019 的某些功能"
product: PowerPoint
category: Guide
source_url: https://support.microsoft.com/zh-CN/Support/known-issues/some-features-of-powerpoint-2019-might-be-disabled-after-installing-the-april-9-2024-update
language: zh-CN
fetched_at: 2026-08-04T11:50:32.309451+00:00
document_id: ms-ad9899c4603c
content_type: Troubleshooting
---

# 安装 2024 年 4 月 9 日更新后，可能会禁用 PowerPoint 2019 的某些功能

> 来源: [https://support.microsoft.com/zh-CN/Support/known-issues/some-features-of-powerpoint-2019-might-be-disabled-after-installing-the-april-9-2024-update](https://support.microsoft.com/zh-CN/Support/known-issues/some-features-of-powerpoint-2019-might-be-disabled-after-installing-the-april-9-2024-update)

# 安装 2024 年 4 月 9 日更新后，可能会禁用 PowerPoint 2019 的某些功能

应用对象
PowerPoint 2019

上次更新时间：2024 年 8 月 14 日

重要

对 Office 2016 和 Office 2019 的支持已于 2025 年 10 月 14 日结束 。 升级到 Microsoft 365 以在任何设备上随时随地工作，并继续获得支持。

获取 Microsoft 365

问题

在 2024 年 4 月 9 日 Office 更新的 PowerPoint 2019 批量许可证安装中禁用了以下功能， ( 版本 1808 内部版本 10409.20028 ) ，以防止可能导致文件损坏和数据丢失的问题。

- “ 插入对象 ”、“ 转换 ”和“ 选择性粘贴 ”对话框中的“ 显示为图标 ”复选框。
- “ 插入对象 ”对话框中的“ 从文件创建 ”选项。
- Shapes.AddOLEObject 方法中的 DisplayAsIcon 和 Link 参数。
- 从“ 粘贴特殊 ”对话框粘贴为“ 图片（Windows 元文件） ”。
- 从 Shapes.PasteSpecial 和 View.PasteSpecial 方法粘贴为 ppPasteMetafilePicture 。

状态：部分已修复

文件损坏已部分解决。 2024 年 7 月 9 日 Office 更新 版本 10412.20006 中已完全还原“显示为图标”功能、“从文件创建”功能以及“Shapes.AddOLEObject”方法中受影响的参数。

以下两个功能仍已删除：

- 从“ 粘贴特殊 ”对话框粘贴为“ 图片（Windows 元文件） ”。
- 从 Shapes.PasteSpecial 和 View.PasteSpecial 方法粘贴为 ppPasteMetafilePicture 。

## 更多资源

询问专家

与专家联系，讨论 PowerPoint 最新资讯和最佳做法，并阅读我们的博客。

PowerPoint 技术社区

”获取社区中的帮助

提出问题，查找来自支持人员、MVP、工程师和其他 PowerPoint 用户的解决方案。

关于答案的 PowerPoint 论坛

建议新功能

欢迎大家踊跃提出建议和反馈！ 分享你的想法。 我们将认真听取你的建议。

提供反馈

## 另请参阅

PowerPoint for PC 中最新问题的修补程序或解决方法

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
