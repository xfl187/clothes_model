# Web Admin Visual Direction

日期：2026-09-24  
状态：视觉方向与三张代表页已确认  
阶段：Visual Direction / Representative High-Fi  
约束：沿用已确认 Web Admin UX，不修改 Product Spec，不更新最终 `DESIGN.md`

## 1. Visual Thesis

### Quiet Control Room / 安静的控制室

Web Admin 是 Quiet Atelier 的后台控制室：与 Android 共享温暖、克制、可信和编辑式气质，但把摄影主导的私人试衣体验转换为由状态、配置和执行记录主导的桌面工作台。

- 视觉锚点从 Android 的人物与衣物摄影，转为“系统结论、当前状态和可追踪关系”。
- 页面使用编辑式标题、强弱明确的数字、规则线和疏密节奏组织信息，不用彩色 KPI 卡片堆出 Dashboard。
- 左侧深色 Sidebar 像稳定的设备机架；右侧暖纸面像可阅读、可标注的工作台。导航与内容形成长期不变的空间记忆。
- 页面上方保持较疏的结论区，下方进入更高密度的表单、表格和诊断数据；密度变化本身构成层级。
- 梅紫只表达当前选择、关键动作和生成配置；绿、琥珀、红继续保持成功、等待/需处理、阻断/破坏的共享语义。
- Surface 只在确有边界时出现：侧栏、右侧 Inspector、决策面板、浮层和粘性操作区。普通内容依靠网格、留白和细规则线组织。
- 深度轻而精准：主画布近乎平面，Inspector 和临时决策层略微前置，不使用玻璃拟态、发光或通用 SaaS 卡片阴影。

即使移除色彩，界面仍应通过以下特征被识别：深色固定侧栏、编辑式结论标题、横向规则线、左侧状态轨、表格与 Inspector 的强密度对比、非对称收紧的关键动作形状。

## 2. 从 Android 继承与转换

### 2.1 跨平台共享

- Quiet Atelier 的暖中性画布、深梅紫关键动作和稳定状态色语义。
- `Noto Serif SC` 只用于少量叙事标题或总体结论，`Noto Sans SC` 承担操作与长时间阅读。
- 图片/对象/状态都不依赖颜色单独表达；文字结论始终存在。
- 主动作使用“单角收紧”的非对称形状；普通控件更克制。
- `waiting_provider` 是等待，不是失败；`needs_attention` 是决策状态，不复用错误样式。
- 用明确状态变化体现 AI 和自动化，不使用霓虹、光晕或任意渐变。

### 2.2 Web-specific 转换

- Android 的摄影主导改为状态与数据主导；Admin 页面不为“统一品牌”强行加入时装图片。
- Android 的宽松触控间距改为 40–44px 行高和 8/12/16px 的高密度桌面节奏，但保留较疏的页面标题区。
- Bottom Navigation 转为 232px 左侧 Sidebar；当前项使用整行 tonal surface + 细窄位置轨，不使用放大的移动端 pill。
- Bottom Sheet 转为右侧 Inspector、Popover 或 Dialog；稳定配置不放入临时 Sheet。
- 移动端卡片实体转为表格行、字段组、规则线和分栏；只让决策与危险操作形成强调 Surface。
- 触觉反馈转为 hover、focus、pressed、保存/测试状态和页面内结果反馈。

## 3. Typography

- 页面总体结论与顶级标题：`Noto Serif SC`，30–36px，500；每页仅 1 个视觉锚点。
- 页面标题、分区标题、字段、导航、表格和操作：`Noto Sans SC`。
- 状态数字：24–40px，tabular figures，靠大小和位置形成层级，不使用彩色数字卡片。
- 表格、时间、容量、版本和任务 ID 使用 tabular figures；任务 ID、版本号和外部执行 ID可使用 `ui-monospace`。
- Overline 仅作辅助目录标记，字距较宽，不承担唯一含义。
- 表格正文不低于 12px；主要表单内容 13–14px；说明 11–12px。

## 4. Density and Composition

- 页面以 12 列内容网格为基础；内容最大宽度约 1440px，但任务诊断允许占满可用区域。
- 页头 28–40px 垂直留白，用于结论、状态和当前动作；进入业务内容后密度明显提高。
- Overview：`总体结论 → 依赖状态带 → 需要处理 / 当前生效配置`，不使用等权 KPI 卡阵列。
- Configuration：`页面状态 → 主表单列 + 右侧验证轨 → 粘性动作区`，字段组用标题、说明和规则线分隔。
- Operations：`过滤工具带 → 高密度表格 → 右侧 Inspector`；选择行与 Inspector 形成明确主从关系。
- 纵向内容组使用 24–32px 间距；同组字段 12–16px；表格行 44–52px。

## 5. Sidebar and Global Chrome

- Sidebar 使用暖黑梅色，而不是纯黑或品牌色大面积铺陈。
- 品牌区使用小型非对称品牌标记、产品名和 `Admin console` 辅助文字；不使用巨大 Logo。
- 导航分组标题低对比，导航项保持紧凑；当前项同时使用浅色文字、tonal surface、左侧 2px 位置轨。
- 顶部全局状态条与 Sidebar 对齐，只显示页面路径、实时/快照状态和管理会话；不加入未确认的搜索、通知或快捷创建。
- Sidebar 在窄桌面收为 64px icon rail；内容不迁移为 Android 导航结构。

## 6. Surfaces, Shape and Depth

- Canvas 与 Paper 保持微小暖色差；主要内容不包整页 Card。
- 普通分区：透明或 Paper，依靠 1px line、留白和标题定位。
- Secondary strip：Mist，用于只读配置摘要、筛选区和低优先级说明。
- Decision panel：Paper + 边框/状态轨，用于 `needs_attention`、测试失败和危险操作影响说明。
- Inspector：略深/略浅于主画布，使用单侧边界与非常轻的内阴影，形成“附着在表格上的仪器面板”。
- 输入框 8px 圆角；普通按钮 8px；主按钮 `10px 10px 3px 10px`；状态不默认使用全圆角 pill。
- 阴影只用于浮层、粘性操作区和 Inspector 边缘，不用于每个分区。

## 7. Tables and Diagnostics

- 表头使用低对比 paper-alt，12px 中等字重；不使用大写英文表头。
- 行间仅水平规则线，不使用完整网格。悬停显示非常轻的 plum wash；选中行增加左侧 2px plum 轨和更明确的 tonal surface。
- 首列 ID 与主对象信息靠左；时间、计数和容量右对齐并使用 tabular figures。
- 状态使用“形状标记 + 文字”，不使用整行彩色 badge。等待为琥珀时钟/圆点，运行中为梅紫进度，成功为绿勾，阻断为红色标记。
- 技术错误以短结论为主；原始脱敏信息放入可展开的诊断块，使用 monospaced 文本和低对比底面。
- Inspector 顶部先显示用户/管理员可理解的结论，再显示候选、外部执行、锁定配置、错误和谱系。

## 8. Forms and Secret Configuration

- 标签永久可见，字段内容与说明形成三层文字层级；placeholder 不承担标签职责。
- 表单按业务责任分区，而不是把所有字段装进一张大 Card。
- Secret 字段显示 `已配置`、更新时间和“覆盖更新”入口，不显示伪造的星号原值。
- 字段级错误贴近输入；跨字段/服务器问题进入测试结果区或提交区。
- 配置测试使用竖向 verification rail：连接、能力、最小生成测试等步骤按真实结果显示，保存不等于启用。
- 重要动作置于底部粘性 action rail；一个主动作，其余降低强调。危险动作与主保存动作保持空间分离。

## 9. Status and Interaction Feedback

- `healthy / active / succeeded`：深绿标记 + 明确文字，不铺大面积绿色。
- `waiting_provider / warning`：琥珀标记或窄轨 + 温和纸面；不使用红色或持续旋转。
- `needs_attention`：琥珀描边决策面板，三个动作并列且后果说明完整。
- `failed / blocked / destructive`：红色只用于结论、边界和危险动作，不把整个页面染红。
- Hover：改变底面和边界，不产生悬浮位移。
- Focus：2px 梅紫 focus ring，保持 WCAG 可见性。
- Pressed：短时加深底面；不改变几何尺寸。
- 保存、测试和刷新结果优先在原位置更新；Toast 只用于不需要持续查看的成功提示。
- 过渡 140–220ms；Inspector 内容切换可使用短距离横向连续性。遵循 reduced motion。

## 10. Representative High-Fi Screens

本轮只验证：

1. `系统概览`：Sidebar、全局框架、总体结论、健康状态与 Dashboard 层级。
2. `LLM Provider 配置详情`：字段组、Secret、验证轨、inactive/active 与动作层级。
3. `任务诊断`：高密度表格、过滤、状态、右侧 Inspector 和 `needs_attention` 决策面板。

本文件中的数值与记录只用于表现真实密度，不新增产品能力。视觉确认后，稳定规则才会进入 `DESIGN.md`，其余页面行为继续保留在 Web Admin UI Spec。
