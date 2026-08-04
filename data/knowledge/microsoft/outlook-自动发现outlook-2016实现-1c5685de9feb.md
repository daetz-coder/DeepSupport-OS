---
title: "自动发现Outlook 2016实现"
product: Outlook
category: Guide
source_url: https://support.microsoft.com/zh-CN/Outlook/outlook-2016-implementation-of-autodiscover
language: zh-CN
fetched_at: 2026-08-04T11:46:48.254419+00:00
document_id: ms-1c5685de9feb
content_type: Troubleshooting
---

# 自动发现Outlook 2016实现

> 来源: [https://support.microsoft.com/zh-CN/Outlook/outlook-2016-implementation-of-autodiscover](https://support.microsoft.com/zh-CN/Outlook/outlook-2016-implementation-of-autodiscover)

# 自动发现Outlook 2016实现

应用对象
Outlook 2016
Outlook for Microsoft 365
Outlook 2019

## 摘要

自动发现是 Outlook 用于获取连接到的服务器的配置信息的功能。 在 Exchange 服务器的Outlook 2016中，自动发现被视为配置信息的唯一事实点，并且必须正确配置和工作才能使 Outlook 完全正常运行。 本文介绍Outlook 2016的当前频道即点即用版本中自动发现的实现。 有关Office 365客户端通道版本的详细信息，请参阅以下Microsoft网站：

Office 365客户端的更新通道版本和内部版本号

Office 365客户端更新通道版本

## 更多信息

### 自动发现计时

自动发现在以下时间运行：

- 在帐户创建期间。
- 按设置的时间间隔收集对提供 Exchange Web 服务功能的 URL 的更改， (OOF、可用性服务等) 。 如果此过程成功，则一小时后再尝试一次。 如果尝试不成功，将在 5 分钟后进行下一次尝试。 由于所有Microsoft Office 应用程序使用的后台任务基础结构，每次尝试可能会交错 25%。
- 响应某些连接故障。 在各种情况下，当连接尝试失败时，Outlook 会启动自动发现任务，以在任何尝试更正连接问题时检索新设置。
- 当另一个应用程序使用 MAPI 调用它时。 有关 MAPI 的详细信息，请参阅以下 MSDN 文章： Outlook MAPI 参考 。

自动发现效率

使用 用户主体名称 (UPN) 来加速自动发现过程。

在已加入域的计算机上，Outlook 需要知道用户的 UPN 才能启动自动发现过程。 UPN 可能已用于登录到 Windows，在这种情况下，Outlook 可以从登录凭据直接访问 UPN。 但是，如果用户使用域\用户名登录 Windows，则 Outlook 仅具有该用户的相同凭据。 若要获取 UPN，Outlook 必须先在目录中查找用户。 Outlook 将请求此查找应追逐引荐。 在复杂环境中，这可能会导致在找到结果之前联系大量 DC。 Outlook 发现用户的 UPN 后，该值将缓存在配置文件中，并且此用户的查找不应再次发生。

若要避免这种情况，用户可以使用 UPN 而不是 domain\username 登录。

ITAR 注意事项

Microsoft Office 365提供的功能可支持客户履行 ITAR 义务。 在 Outlook 中自动发现功能的上下文中，此功能集包括策略设置和行为，以确保用于自动发现的服务终结点符合主权云要求。 具体而言，在自动发现过程 ( 步骤 4 和步骤 11) 中列出的Office 365特定步骤中，可以使用策略控制来确保在自动发现过程中使用适当的服务终结点。

自动发现过程 每次 Outlook 需要自动发现信息时，它都会使用一组有序步骤来尝试检索包含配置设置的 XML 有效负载。 其中许多步骤都可以通过使用 组策略 对象 (GPO) 来控制，并且 GPO 值包含在步骤说明中。

#### 步骤 1：检查重启方案

在某些情况下，例如，在 Outlook 运行时添加第二个帐户时，自动发现有效负载将缓存到本地文件，以在 Outlook 客户端重启期间使用。 第一个自动发现步骤是在注册表中检查一些特殊的“启动”信息，以告知 Outlook 你处于这些重启方案之一，并从特殊的本地文件中读取自动发现有效负载。 这种情况很少见，通常不是一般自动发现问题的原因。 对于此步骤，如果 Outlook 确定你处于此特殊启动方案，并且检索自动发现 XML 数据的尝试失败，则整个自动发现尝试将失败。 不会尝试其他步骤。

此步骤没有特定的策略控制。

#### 步骤 2：检查本地数据首选项

Outlook 提供了一个 GPO，允许管理员部署要用于配置的特定自动发现 XML 文件。 如果管理员已部署此注册表值并种子设定 autodiscover.xml 文件，Outlook 将从此文件读取自动发现有效负载。 这种情况同样不常见，通常不是导致一般自动发现问题的原因。 如果此步骤未检索有效负载，Outlook 将转到步骤 3。

有关自动发现 XML 的详细信息，请参阅以下 TechNet 文章： 计划在 Outlook 2010 中自动配置用户帐户

注意 本文是为 Outlook 2010 创建的。 但是，它仍然与更高版本的 Outlook 相关。

此步骤的策略控制值如下： PreferLocalXML 。

#### 步骤 3：检查 LKG) 数据 (上一次已知良好

当自动发现通过任何步骤成功检索 XML 有效负载时，可将有效负载作为“最后一个已知良好”配置在本地缓存。 获取自动发现有效负载的第一个通常成功的方法是来自此最后一个已知良好的文件。 最后一个已知良好的 XML 文件的路径来自 Outlook 配置文件。 LKG 步骤仅用于发现主邮箱配置。 如果自动发现查找适用于非主邮箱 (备用邮箱、委托邮箱、公用文件夹邮箱、组邮箱等) ，则会自动跳过 LKG 步骤。 如果此步骤未检索有效负载，Outlook 将转到步骤 4。

此步骤的策略控制值如下： ExcludeLastKnownGoodURL 。

#### 步骤 4：检查 O365 作为优先级

Outlook 使用一组试探法来确定提供的用户帐户是否来自Office 365。 如果 Outlook 确信你是 O365 用户，则会尝试从已知的 O365 终结点检索自动发现有效负载， (通常 https://autodiscover-s.outlook.com/autodiscover/autodiscover.xml 或 https://autodiscover-s.partner.outlook.cn/autodiscover/autodiscover.xml) 。 如果此步骤未检索有效负载，Outlook 将转到步骤 5。

此步骤的策略控制值如下所示：

ExcludeExplicitO365Endpoint 。

ITAR 注意事项

默认情况下，Outlook 查询已知终结点以检索自动发现有效负载。 绕过此步骤的现有策略仍然有效，可用于转到步骤 5，而无需尝试终结点。 或者，还有一个新策略指示 Outlook 查询中心Office 365配置服务，以检索从中检索自动发现有效负载的相应 URL。 从概念上讲，该过程的工作方式如下：

- 设置新策略。
- 在自动发现过程的步骤 4 期间，Outlook 会查询Office 365配置服务。
- 该服务确定哪个 (（如果任何) 特殊 ITAR 需求对指定用户有效），并使用 UPN 的域信息返回该用户的相应 URL。
- Outlook 尝试从服务提供的 URL 中检索自动发现有效负载。

新功能使用Office 365配置服务的策略控制值为 EnableOffice365ConfigService 。

注意

从内部版本 16.0.9327.1000 起， 不再使用 EnableOffice365ConfigService 策略。

#### 步骤 5：检查 SCP 数据

如果计算机已加入域，Outlook 将执行 LDAP 查询以检索返回自动发现 XML 路径的服务连接点数据。 然后尝试对 SCP 查找返回的每个 URL 进行尝试，以尝试检索自动发现有效负载。 如果此步骤未检索有效负载，Outlook 将转到步骤 6。

有关 SCP 的详细信息，请参阅以下 MSDN 文章： 使用服务连接点发布 。

此步骤的策略控制值如下： ExcludeScpLookup 。

#### 步骤 6：检查根域

对于此步骤，Outlook 以 https://< domain>/autodiscover/autodiscover.xml 格式从初始地址的域名生成 URL，并尝试从生成的 URL 检索有效负载。 由于许多根域未针对自动发现进行配置，因此 Outlook 会有意将尝试检索期间发生的任何证书错误静音。 如果此步骤未检索有效负载，Outlook 将转到步骤 7。

此步骤的策略控制值如下： ExcludeHttpsRootDomain 。

#### 步骤 7：检查自动发现域

对于此步骤，Outlook 会以 https://autodiscover 格式从初始地址的域名生成 URL。<domain>/autodiscover/autodiscover.xml 并尝试从生成的 URL 检索有效负载。 由于此 URL 通常是自动发现数据的主要 URL，因此 Outlook 不会将尝试检索期间发生的任何证书错误静音。 如果此步骤未检索有效负载，Outlook 将转到步骤 8。

此步骤的策略控制值如下： ExcludeHttpsAutoDiscoverDomain 。

#### 步骤 8：检查本地数据

在步骤 2 中，Outlook 检查管理员是否已部署策略，以专门检查自动发现有效负载作为首选项。 如果没有策略，但前面的步骤未检索有效负载，Outlook 现在会尝试从本地文件检索有效负载，即使没有 PreferLocalXML 设置。 如果此步骤未检索有效负载，Outlook 将转到步骤 9。

此步骤没有策略控制。

#### 步骤 9：检查 HTTP 重定向

对于此步骤，Outlook 会将请求发送到自动发现域 URL (http://autodiscover。<domain>/autodiscover/autodiscover.xml) 并测试重定向响应。 如果返回的是实际的自动发现 XML 有效负载而不是重定向，Outlook 将忽略实际的自动发现 XML 响应，因为检索该响应时没有安全 (http) 。 如果响应是有效的重定向 URL，Outlook 会遵循重定向并尝试从新 URL 检索有效负载 XML。 Outlook 还将执行证书检查，以防止重定向到此步骤中可能有害的 URL。 如果此步骤未检索有效负载，Outlook 将转到步骤 10。

此步骤的策略控制值如下： ExcludeHttpRedirect 。

#### 步骤 10：检查 SRV 数据

对于此步骤，Outlook 对“_autodiscover._tcp”进行 DNS 查询。<域名>“并循环访问结果，查找使用 https 作为其协议的第一条记录。 然后，Outlook 会尝试从该 URL 检索有效负载。 如果此步骤未检索有效负载，Outlook 将转到步骤 11。 此步骤的策略控制值如下： ExcludeSrvRecord 。

#### 步骤 11：检查 O365 是否为故障安全

如果上述所有步骤均未返回有效负载，Outlook 将使用限制较少的启发式方法集来决定对 O365 终结点的最终尝试是否可能有所帮助。 如果 outlook 确定尝试是值得的，它会尝试已知的 O365 自动发现终结点，以防该帐户是 O365 帐户。 此尝试使用与步骤 4 相同的目标 URL，但不同之处在于它是作为最后手段尝试的，而不是在自动发现过程中的早期。

此步骤的策略控制值如下： ExcludeExplicitO365Endpoint 。

ITAR 注意事项

如果 Outlook 进入此步骤并且未成功检索自动发现有效负载，将执行两个测试，以查看是否应尝试已知的Office 365终结点。 首先，如果邮箱是使用者帐户 (例如 outlook.com) ，则尝试使用已知终结点。 其次，如果邮箱被确定属于没有 ITAR 要求的域，则尝试使用已知终结点。 如果邮箱被确定为商业邮箱，并且属于具有 ITAR 要求的域，则不会尝试已知的Office 365终结点。 在未来的版本中，步骤 11 可能会移动到与步骤 4 相同的逻辑，并调用 Office 365 配置服务。 进行该更改后，本文将更新以反映新的流程步骤。

“自动发现过程”部分中的重定向处理步骤 9 是处理不安全的重定向数据的显式步骤。 在任何其他安全步骤中，对于任何检索自动发现 XML 有效负载的尝试，终结点的一个可能的响应是重定向响应。 此响应告知 Outlook 重定向到新的不同 URL 以尝试检索有效负载。 此外，重定向数据可能包含一个新的不同的电子邮件地址，用作自动发现尝试的目标地址。 Outlook 将三个单独的响应视为“重定向响应”：

- HTTP 状态代码 (301、302) 以及新 URL
- HTTP 状态代码为 200，但有效负载 XML 指示 Outlook 重定向到其他 URL
- HTTP 状态代码为 200，但有效负载 XML 指示 Outlook 使用不同的 smtp 地址作为目标地址。

在案例 1 和 2 中，如果协议为 https，Outlook 会尝试从新 URL 检索自动发现 XML。 不尝试使用不安全 (http) URL。 此外，即使新 URL 中的协议是 https，Outlook 也会检查证书信息，以提供额外的安全措施。

对于案例 3，Outlook 从头开始启动整个自动发现过程。  如果使用新电子邮件地址尝试了 (1-11) 的所有步骤，则 Outlook 将返回到原始电子邮件地址，转到步骤 5，并继续尝试检索具有原始地址的 XML 有效负载。

例外 自动发现过程部分中的步骤是 Outlook 如何尝试获取自动发现有效负载的一般规则。 存在各种优化和异常尝试，可能会稍微改变过程。 例如，在创建新帐户时，Outlook 在内部跳过“最后一个已知良好 (LKG) 数据) ”步骤 3 (检查，因为它尚不能具有最后一个已知良好的条目。  同样，如果尝试因使用当前配置信息出错而触发，则 Outlook 会有意再次自动发现，而不要使用 LKG 信息，因为可能最后已知的良好信息导致失败。

策略控制 自动发现进程部分定义的策略值可以是基于策略的注册表值，也可以是基于策略的值。  通过 GPO 或手动配置策略密钥进行部署时，设置优先于非策略密钥。

非策略密钥：HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\AutoDiscover

策略密钥：HKEY_CURRENT_USER\Software\Policies\Microsoft\Office\16.0\Outlook\AutoDiscover

每个值的类型为 DWORD 。

PreferLocalXML 与其他控件值不同，因为设置为 1 将 Outlook 设置为在此过程中打开该步骤。  对于剩余值，设置为 1 告知 outlook 关闭或跳过关联的步骤。 例如，将 值 ExcludeHttpsRootDomain 设置为 1 会将 Outlook 设置为不执行过程中的步骤 6。

其他注册表控件

Outlook 提供了几个其他基于注册表的配置选项，这些选项可能会影响自动发现过程：

使用 Office 365 配置服务

键：HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\AutoDiscover 值：EnableOffice365ConfigService 默认值：0 数据：将此 DWORD 数据设置为 1 以强制 Outlook 调用Office 365配置服务以检索相应的自动发现 URL。

HTTP 超时设置

键：HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\AutoDiscover 值：超时 默认值：25 秒 最小值：10 秒 最大值：120 秒

信息：指定的超时用作 WinHttpSetTimeout 设置 。 指定的数据将传递给 WinHttpSetTimeouts API 的所有四个参数。 这可能会使无法访问的 HTTP 请求能够更快地超时，从而提高整体性能。 这些设置还可以通过将超时设置增加到大于 25 秒的超时设置来允许花费超过默认值 25 秒的 HTTP 请求成功。 Mapi/Http 协议控制

键：HKEY_CURRENT_USER\Software\Microsoft\Exchange 值：MapiHttpDisabled 默认值：0 数据：1 = 协议已禁用;0 = 协议已启用

信息：此值不位于自动发现键下。 这是一个常规设置，用于控制 Outlook 是否可以尝试使用 Mapi/Http 协议堆栈连接到 Exchange。 Outlook 2016中的默认值不禁用此协议。 这允许自动发现进程向发现过程添加一个特殊的标头 (X-MapiHttpCapability：1) ，以便可以评估和处理 Mapi/Http 协议设置。 旧式身份验证协商控制

键：HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\RPC 值：AllowNegoCapabilityHeader 默认值：0 数据：1 = 添加标头;0 = 未添加标头

信息：请注意，此值不在自动发现键下。 此设置控制是否将身份验证协商标头添加到 http 请求。 标头的内容取决于客户端计算机的身份验证功能。 示例标头可能是：“X-Nego-Capability：Negotiate、pku2u、Kerberos、NTLM、MSOIDSSP”。 此注册表值及其添加的标头很少在任何新式身份验证堆栈中使用，并且不太可能以负或正方式影响 tAodiscover 进程。 证书错误处理

键：HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\AutoDiscover 值：ShowCertErrors 默认值：0 数据：1 = 显示证书警告/错误;0 = 不显示证书警告

信息：此值控制 Outlook 如何处理执行 http 任务时收到的证书错误和警告。 在某些情况下，Outlook 可能会替代此设置， (“自动发现过程”部分中的步骤 6) ，但对于一般情况，如果启用此设置，Outlook 会提示显示证书错误或警告的安全对话框，并允许用户确定或取消 Http 请求。 用户可决定忽略三个特定的证书错误，并让 Outlook 重试 http 请求：

- WINHTTP_CALLBACK_STATUS_FLAG_CERT_DATE_INVALID – 证书属性中的日期存在问题
- WINHTTP_CALLBACK_STATUS_FLAG_CERT_CN_INVALID – 证书属性中的公用名存在问题
- WINHTTP_CALLBACK_STATUS_FLAG_INVALID_CA – 证书属性中的证书颁发机构存在问题 有关这三种证书错误状态的详细信息，请参阅 WINHTTP_STATUS_CALLBACK回调函数

代理身份验证处理

键：HKEY_CURRENT_USER\Software\Microsoft\Office\16.0\Outlook\HTTP\ 值：AllowOutlookHttpProxyAuthentication 默认值：0 数据：1 = 允许 Outlook 处理来自代理服务器的身份验证质询;0 = 以静默方式使来自代理服务器的身份验证质询失败

信息：此注册表值允许放宽安全配置，并在Microsoft知识库的以下文章中进行了详细介绍：

3115474 MS16-099：Outlook 2010 安全更新说明：2016 年 8 月 9 日

### 自动发现其他协议

Outlook 还使用自动发现作为一项功能来发现和配置Exchange ActiveSync (EAS) 帐户。 EAS 自动发现过程和决策与本文中所述的步骤不同。 例如，EAS 实现不实现 O365 终结点逻辑，并且没有用于检查 SCP 位置的步骤。 本文的范围是介绍 Outlook 用于自动发现尝试从 Exchange 获取基于 MAPI 的协议的详细步骤。

## 参考资料

有关自动发现的旧信息，请参阅Microsoft知识库中的以下文章：

2212902 在 \Autodiscover 项下具有注册表设置时出现意外的自动发现行为

有关自动发现的详细信息，请参阅以下Microsoft文章：

Exchange 的自动发现

自动发现服务

---

本页由 DeepSupport OS 研究爬虫采集自 Microsoft 公开支持文档，仅用于本地演示检索；请遵守 Microsoft 服务条款与版权要求。
