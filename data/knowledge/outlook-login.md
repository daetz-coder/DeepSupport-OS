# Outlook 无法登录 Contoso 账号

**product:** Outlook  
**category:** Login  
**language:** zh-CN  
**content_type:** Troubleshooting

## 现象

用户打开 Outlook 后提示无法登录、密码错误，或反复出现凭据提示框。

## 可能原因

1. 账号被锁定（多次输错密码）
2. MFA 验证失败或验证器不可用
3. 许可证异常导致应用无法完成身份验证
4. 本地凭据缓存损坏

## 排查步骤

1. 确认用户邮箱与 UPN
2. 查询账号状态（active / locked / disabled）与 MFA 状态
3. 若账号锁定，走密码重置审批流程
4. 确认设备上 Office 版本与系统时间
5. 必要时创建 IT 工单并附带诊断摘要

## 参考

本文件为 DeepSupport OS 示例知识，正式环境应通过 RAGLab 检索 Microsoft 支持文档。
