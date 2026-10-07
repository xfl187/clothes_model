# Product Visual Design System

状态：Android `Quiet Atelier` 与 Web Admin `Quiet Control Room` 视觉方向已确认  
适用范围：Android V1 / V1.1 共用界面语言；Web Admin 桌面管理界面  
行为权威：产品行为与版本页面职责仍以 Product Spec、Product Flow 和对应 UI Spec 为准

本文只记录跨页面稳定复用的视觉与交互语言。页面流程、Screen Inventory、验收场景和临时探索不在本文重复。

## Visual Direction

### Quiet Atelier / 私人时装工作室

产品应像一间安静、可信、长期使用的私人试衣工作室，而不是促销型电商、社交衣橱或带有霓虹装饰的 AI 工具。

- 摄影是主要视觉材料。人物、衣物和结果图片承担情绪与可信度，界面 chrome 主动退后。
- 编辑式排版通过尺度、字重和留白建立层级。Android 全部使用设备优化的中文无衬线字体，保证模拟器与真机上的稳定清晰度；Web 结论标题仍可保留衬线气质。
- 大面积暖中性背景营造私人感；深梅紫只用于生成、选择和关键导航，不铺满所有容器。
- 通过尺度、留白、图像比例和前后景建立层级，不依赖彩色卡片堆叠。
- AI 的存在通过生成状态、连续过渡和明确反馈体现，不使用霓虹、光晕、任意渐变或“未来感”装饰。
- 形状具有家族关系但不完全相同。图像和主要动作使用“单角收紧”的非对称圆角；状态、筛选和普通表单使用更克制的形状。

即使移除色彩，这套界面仍应能通过摄影占比、编辑式标题、非对称图像轮廓和疏密节奏被识别。

### Quiet Control Room / 安静的控制室

Web Admin 是同一产品的后台控制室。它继承 Quiet Atelier 的温暖、克制、可信和编辑式排版，但把视觉锚点从摄影转换为系统结论、配置验证和可追踪执行记录。

- 深色固定 Sidebar 像稳定的设备机架，暖纸面主区像可阅读、可标注的工作台。
- 页面上方使用较疏的结论区，下方进入高密度表单、表格和诊断；密度变化本身建立层级。
- 状态、配置版本和执行关系是主要视觉材料。管理页不为品牌统一而强行加入时装摄影。
- 普通内容依靠网格、留白和规则线组织；只在 Inspector、决策面板、浮层和粘性动作区建立明确 Surface。
- 不使用通用 SaaS KPI 卡阵列、霓虹 AI 装饰、玻璃拟态或每区一张圆角 Card。

即使移除色彩，Web Admin 仍应通过深色侧栏、编辑式结论标题、横向规则线、状态轨、表格与 Inspector 的密度对比和非对称主动作形状被识别。

## Color

### Light theme

| Role | Token | Value | Use |
|---|---|---:|---|
| App canvas | `atelierCanvas` | `#F3EFE9` | edge-to-edge 页面背景 |
| Primary surface | `atelierPaper` | `#FBF8F3` | 内容底面、底部导航、浮层 |
| Secondary surface | `atelierMist` | `#ECE7E1` | 次级区域、占位、禁用模式 |
| Primary text | `atelierInk` | `#241F23` | 标题、正文、关键数字 |
| Secondary text | `atelierMuted` | `#5F565D` | 元数据、说明、非关键状态 |
| Primary accent | `atelierPlum` | `#69465F` | 选择、生成动作、当前导航 |
| Strong accent | `atelierPlumDeep` | `#4A3043` | 主按钮及高强调动作 |
| Accent container | `atelierBlush` | `#DCC5CF` | 当前导航、选择辅助底色 |
| Divider | `atelierLine` | `#948890` | 清晰可辨的分隔与输入边界 |
| Success | `atelierSuccess` | `#426C56` | 完成、已保留、质量通过 |
| Warning surface | `atelierWarning` | `#F3DFB7` | 可继续的质量风险、等待 |
| Warning text | `atelierWarningInk` | `#6B4B18` | 警示标题和说明 |
| Error | `atelierError` | `#A7433F` | 阻断、失败、破坏性后果 |
| Scrim | `atelierScrim` | `#241F23` at 64% | 图片覆层、模态背景 |

### Dark theme

暗色主题保持暖黑与梅紫关系，不把界面变成高饱和“AI 深色模式”。

| Role | Value |
|---|---:|
| Canvas | `#171417` |
| Primary surface | `#211D20` |
| Secondary surface | `#2B262A` |
| Primary text | `#F3ECEF` |
| Secondary text | `#D1C6CC` |
| Primary accent | `#D5AFC3` |
| Accent container | `#563A4E` |
| Divider | `#71656C` |
| Success | `#8FC3A2` |
| Warning surface / text | `#4B391E` / `#F1D18E` |
| Error | `#F1A19B` |

- 动态取色默认关闭，避免系统壁纸改变产品身份与状态语义。
- 图片覆层必须按实际图像检测可读性；必要时使用底部 scrim，不给所有图片统一蒙色。
- 状态始终同时使用文字、图形或位置，颜色只作辅助。
- 正文、状态和操作满足 WCAG AA 对比度；图片上的小字目标不低于 4.5:1。

## Typography

### Font families

- Android display / UI / body：设备系统中文无衬线字体，用较明确的字号和字重区分层级，避免部分模拟器缺少衬线字形时回退成细体。
- Web editorial：页面结论与少量对象标题可继续使用衬线字体；表单、状态与操作使用无衬线字体。
- 数字、百分比和运行时间使用 UI 字体的 tabular figures；不混用装饰性数字字体。
- 字体作为本地资源随 App 提供，避免网络字体导致布局漂移。

### Type roles

以下角色是 Android 基准：

| Role | Size / line height | Weight | Use |
|---|---:|---:|---|
| Display Large | 36sp / 42sp | 600 | 极少量品牌或空状态主句 |
| Display Medium | 30sp / 36sp | 600 | 首页和关键结果主标题 |
| Headline | 24sp / 30sp | 600 | 页面主标题 |
| Title Large | 20sp / 26sp | 700 | 顶栏或区域标题 |
| Title Medium | 16sp / 22sp | 650 | 卡片实体、重要状态 |
| Body Large | 16sp / 24sp | 500 | 关键解释、表单内容 |
| Body Medium | 15sp / 22sp | 500 | 默认正文 |
| Label Large | 14sp / 20sp | 700 | 主次按钮、筛选 |
| Label Medium | 13sp / 18sp | 650 | 元数据、状态 |
| Overline | 11sp / 16sp | 750 | 英文眉题；字距 0.12em |

- Android 不依赖衬线字体承担层级；标题使用更高字重，长段状态、错误、表单和按钮保持统一无衬线字形。
- 关键状态和恢复动作不截断；大字号下允许换行和增加容器高度。
- 中文不使用全大写。英文 overline 只作辅助，不承担唯一信息。

### Web Admin type roles

| Role | Size / line height | Weight | Use |
|---|---:|---:|---|
| Page verdict | 30–36px / 38–44px | 500 | 系统总体结论、顶级配置对象标题 |
| Page title | 26–30px / 34–38px | 500 | 普通管理页面标题 |
| Section title | 14–16px / 20–24px | 650 | 表单分区、Inspector 分组 |
| Body | 13–14px / 20–22px | 400 | 表单内容、主要说明 |
| Dense body | 12–13px / 18–20px | 400 | 表格与诊断信息 |
| Label / metadata | 11–12px / 16–18px | 600 | 字段、状态、辅助数据 |
| Overline | 10–11px / 16px | 700 | 英文目录标记；字距 0.12–0.17em |

- Web 的任务 ID、版本、时间和容量使用 tabular figures；技术 ID 可使用 `ui-monospace`。
- 衬线字体在 Web 中仍只承担页面结论和少量对象标题，不进入表格、表单或错误正文。

## Spacing and Density

基础网格为 4dp，常用间距为 `4 / 8 / 12 / 16 / 20 / 24 / 32 / 40` dp。

- 手机页面水平安全边距：16dp；强调型首屏可使用 20dp。
- 顶栏与首个主内容区：12–16dp。
- 同组控件：8–12dp；相邻内容组：20–24dp；叙事型大区块：32dp。
- 图片网格 gutter：8dp；结果主次画幅 gutter：8dp。
- 使用留白分组优先于新增卡片、分割线或背景色。
- 页面密度允许变化：首页疏、素材网格中等、任务与技术详情相对密。

Web Admin 使用同一 4px 基础网格，但采用桌面密度：

- Sidebar 宽度约 232px；窄桌面收为约 64px icon rail。
- 页面标题区垂直留白 28–40px；主要内容组 24–32px；同组字段 12–16px。
- 表格行高 44–52px；工具条和表头保持紧凑，不缩小必要文字。
- 内容通常基于 12 列网格；任务诊断可使用完整可用宽度，普通配置页保持可读最大宽度。
- Overview 疏、Configuration 中等、Operations 高密；不强求所有页面使用相同间距。

## Shape

形状用于区分内容、动作和系统反馈，而不是给所有元素加同一大圆角。

- Hero / 主要结果：`28dp 28dp 8dp 28dp`，形成单角收紧的品牌轮廓。
- 素材缩略图：`18dp 18dp 6dp 18dp`。
- 主按钮：`16dp 16dp 6dp 16dp`；最小高度 52dp。
- 次按钮和普通表单：12dp。
- 筛选 chip 与状态标签：全圆角，但仅用于短文本和单一状态。
- Sheet：顶部 28dp，底部随系统窗口；Dialog：20dp。
- 不在嵌套容器中重复三层圆角；图片已形成边界时不再外包 Card。

Web Admin 的形状更克制：

- 普通输入与次按钮：6–8px。
- 主按钮：`10px 10px 3px 10px`，保留单角收紧的家族特征。
- 当前 Sidebar 项：`8px 8px 3px 8px`，同时使用左侧位置轨。
- 表格、规则线分区和 Inspector 默认不增加圆角。
- 状态默认使用图形标记 + 文字；只有短、独立的枚举值才使用全圆角标签。

## Surfaces and Depth

- 默认页面以 `atelierCanvas` 和 `atelierPaper` 的细微色差建立前后景。
- 列表和说明优先使用留白或 1dp 分隔，不默认使用 elevation。
- 浮层、底部 sheet 和临时工具条可使用 2–6dp 的柔和阴影。
- 主要图片可与纸面直接相接，不加白色 Card 边框。
- 半透明只用于图片覆层或临时悬浮控制；不使用全屏玻璃拟态。
- 按压反馈使用低强度 plum tint 和 Android ripple；不改变布局尺寸。

Web Admin：

- 主画布近乎平面，以 `atelierCanvas / atelierPaper / atelierMist` 的微小色差和规则线建立层次。
- Sidebar 使用暖黑梅色；不使用纯黑，也不把品牌色铺满主内容。
- Inspector 与主表格通过单侧边界、轻微 tonal 差和极弱内阴影建立附着关系。
- 决策面板使用状态轨或描边，不把整个区域染成高饱和状态色。
- 阴影只用于浮层、Dialog、粘性动作区和 Inspector 边缘；普通内容组不使用 elevation。

## Imagery

- 首页 hero 使用 4:5 至 3:4 的人物时装摄影；构图应保留人体与衣物阅读空间，避免只有脸部特写。
- 人物素材默认 3:4，优先 `ContentScale.Crop`，但不得裁掉当前衣物类型所需的目标区域。
- 衣物素材默认 3:4；平铺、商品图可在暖灰底上使用 `ContentScale.Fit`，实拍图使用 Crop。
- 结果以图像占据页面主要面积。候选被选中时可放大为主画幅，其余成为次画幅；这只是视觉层级，不改变候选语义。
- 质量风险贴近受影响图片，在不遮挡关键衣物区域的位置显示。
- 加载使用低对比骨架和保持比例的占位；加载失败显示“图片暂不可用”；主动删除显示“素材已删除”，两者图形和文案不同。
- 原图与结果必须明确标注；对比控件的分隔线、拖柄和标签在任何图像上保持可见。

## Navigation Principles

- 底部导航保持 `首页 / 素材 / 历史` 三项。当前项使用浅梅色异形底而不是默认 Material pill。
- 创建、任务、结果和编辑器是主导航之上的专注型全屏目的地，不新增底部导航项。
- 系统返回与顶栏返回结果一致；支持 predictive back。
- 长任务离开页面不等于取消。返回首页或历史后必须保持任务可恢复。
- 仅在存在未提交编辑或真实破坏性后果时拦截返回。
- edge-to-edge 渲染，但文本、操作和拖柄必须避开状态栏、手势区与显示切口。

Web Admin：

- 主导航固定为 `概览 / 配置 / 运行维护` 三组 Sidebar；分组标题不可点击。
- 当前项使用 tonal surface、明亮文字和左侧 2px 位置轨共同表达，不只依赖颜色。
- 顶栏只显示路径、实时/快照状态和管理会话；不加入未确认的搜索、通知或快捷创建。
- 桌面详情优先使用右侧 Inspector 或独立详情路由，不迁移 Android Bottom Sheet。
- 窄桌面下 Sidebar 收窄为 icon rail；任务 Inspector 退化为表格后的独立详情区域。

## Component Language

### Primary Action

- 每屏最多一个高强调主动作。
- 深梅紫背景、白色文字、尾部方向箭头；箭头只强化前进语义，不代替标签。
- 处理中主动作变为明确进度状态；不可执行时同时显示原因，不只降低透明度。

### Asset Tile / Asset Picker

- 图像本身是交互表面，不额外套白卡。
- 选中态组合使用 2dp 深梅描边、右上勾选标记和网格后的文字摘要。
- “从相册导入”使用虚线边界和明确文字，不伪装成已有素材。
- 实验性来源、质量风险和上传状态贴近对应素材。
- 人物与衣物复用同一选择语言，但保留各自已确认的独立步骤与筛选。

### Task Row / Job Status Panel

- 行内同时呈现缩略图、用户可读任务名、状态说明和关键进度。
- `running` 可使用确定或不确定进度，但不能伪造完成时间。
- `waiting_provider` 使用温和警示语义，并明确“恢复后自动继续”和已等待时间。
- `needs_attention` 是独立决策面板，不复用普通失败卡；三个恢复动作必须完整可见。
- 技术配置和执行谱系默认折叠，通过 progressive disclosure 查看。

### Candidate Gallery

- 成功图片先出现；失败或取消候选保留在图片区域之后。
- 当前候选可用主次画幅表示，但同时提供文字“已选择”和可访问语义。
- 操作按“检查 / 保存 / 修正”分组；破坏性操作进入更多菜单或明确确认流程。
- “同参数重试”与“修正后重新生成”使用不同标签。

### Form and Settings

- 输入框使用 1dp 边界与 12dp 圆角，不默认填充大面积 accent 色。
- 标签始终可见，不只依赖 placeholder。
- 字段错误贴近原因；服务器或跨字段问题在提交区呈现。
- Provider 变化使用前后对照，说明原因，并在提交前确认；不静默切换。

Web Admin 的配置表单补充规则：

- 页面使用“分区介绍列 + 字段列 + 可选验证轨”，不把所有字段放进一张大 Card。
- Secret 只显示已配置状态、更新时间和覆盖入口，不回显原值或伪造可读掩码。
- 保存、验证、启用和设为默认是独立状态与动作；视觉上不得合并。
- 连接、能力和最小试运行使用竖向 verification rail 表达真实结果与未完成步骤。
- 重要动作进入底部 action rail；一个主动作，危险动作与保存动作保持空间分离。

### Web Admin Table / Diagnostic Inspector

- 表头使用低对比 secondary surface；行间只使用水平规则线，不画完整网格。
- Hover 使用轻微 plum wash；选中行增加左侧 2px plum 轨和更明确的 tonal surface。
- 首列展示稳定 ID 与对象摘要；时间、计数和容量使用 tabular figures 并按数值对齐。
- 状态由形状标记、文字和位置共同表达；不把每个状态做成彩色胶囊。
- Inspector 先显示管理员可理解的结论，再显示候选、外部执行、锁定配置、错误与谱系。
- 原始外部错误只以脱敏、monospaced 的诊断块渐进披露。

### Before / After Compare

- 原图与结果在图内固定标注。
- 拖柄触控区域至少 48dp，视觉线可更细。
- 提供 TalkBack 可操作的步进调整和“显示原图 / 显示结果”替代动作。

### Mask Editor

- 图片尽可能占据可用空间，工具条贴近底部安全区。
- 当前工具同时使用图形、文字和选中容器表达。
- 遮罩使用半透明 plum，并提供边缘描线；支持单独切换遮罩预览。
- 撤销不可用时保持可见但说明状态；离开未提交编辑前确认。

## Status and Feedback

| Status | Visual treatment | Required communication |
|---|---|---|
| Queued | cool-neutral marker | 已保存、等待原因、可取消范围 |
| Waiting provider | amber clock / warm surface | 临时离线、已等待时长、会自动继续 |
| Preparing | neutral progress | 正在上传或预处理、取消为尽力而为 |
| Running | plum progress | 候选级状态、已运行时间、可离开页面 |
| Needs attention | outlined decision panel | 自动推进已停止；重新查询、明确重试、结束失败 |
| Succeeded | green check | 成功数量和后续结果操作 |
| Partial success | green + warning composition | 成功已保留、失败项可单独处理 |
| Failed | red marker, no success imagery | 原因、原参数重试、谱系入口 |
| Cancelled | neutral stop marker | 已取消范围和保留内容 |

- Snackbar 只用于短暂、可撤销或无需持续查看的反馈。
- 影响任务状态的操作优先使用页面内反馈；不对每次选择显示 Snackbar。
- 重要状态变化可产生一次轻触觉反馈；失败不连续震动。
- 破坏性删除说明“删除什么”和“保留什么”。

## Motion

- 页面进入：220–280ms，standard easing；共享图片从素材缩略图扩展到确认或详情时保持空间连续性。
- 选择：描边与勾选 140–180ms，同步轻触觉反馈。
- 候选生成完成：使用轻微淡入与 4–8dp 上移，不使用闪光或庆祝动画。
- 结果主次切换：240ms，图片位置与圆角连续过渡。
- `waiting_provider` 不使用持续旋转制造紧迫感；使用静态时钟和低频状态呼吸即可。
- 遵循系统 reduced motion；关闭非必要位移和呼吸，保留即时状态替换。

Web Admin：

- Hover、focus 和 pressed 反馈 120–180ms，不产生浮起或几何位移。
- 页面与 Inspector 内容切换 160–220ms；只使用轻微淡入或短距离连续性。
- 测试、保存、刷新和状态变化优先在原位置过渡，不用全页 loading 覆盖已知信息。
- `waiting_provider` 在 Web 同样不持续旋转或制造紧迫感。

## Accessibility

- 所有主要触控目标至少 48dp；图片上的圆形按钮视觉尺寸可小于 48dp，但命中区域不能缩小。
- TalkBack 顺序先页面标题和总体状态，再主内容，再上下文操作。
- 图片操作标签包含对象，例如“收藏候选 2”“取消候选 1”。
- 选择、风险、进度和错误不只通过颜色表达。
- 字体放大到 200% 时，状态、错误和主操作允许换行，不使用固定文本高度。
- 素材与结果网格按宽度和字体缩放减少列数，必要时退化为单列。
- 任务更新只播报阶段性变化，不播报每个百分比。
- 对比和遮罩编辑提供非手势替代操作；焦点在工具切换后保持可预测。

Web Admin：

- 所有交互元素具有清晰的 2px focus ring；键盘顺序遵循 Sidebar → 页面标题/工具 → 主内容 → Inspector。
- 精细指针下控件可紧凑，但主要按钮与表格行保持足够命中区域；触控设备上扩大至约 44px。
- 表格在窄宽度允许受控横向滚动；关键 ID、状态和主要操作不能只在 hover 出现。
- Inspector 退化为独立详情时保持标题、状态和操作顺序，不丢失表格选择上下文。
- 实时任务更新只播报阶段性变化；筛选、保存和测试结果使用适度的 `aria-live`。

## Android and Material 3 Adaptation

- Material 3 提供语义、状态、ripple、焦点、系统栏、Dialog/Sheet 行为和 Compose 可访问性基础。
- 最终视觉不得直接使用默认 `Card + Button + ColorScheme` 组合替代本文的构图、图像、形状和字体语言。
- 可在 Compose 中使用自定义 `Shape`、`Surface`、`AnimatedContent`、共享元素和自定义绘制实现本系统。
- 紧凑手机是 V1 主目标；较宽窗口增加内容最大宽度和留白，不无条件拉伸图片。
- 横屏或大屏时，选择器可采用左侧预览、右侧网格；导航在真正需要时才适配 rail，不提前改变信息架构。
- 使用 Android Photo Picker；系统权限、键盘、分享和下载继续遵循平台标准交互。
- 重连、进程恢复和重新认证后，服务端任务状态是权威来源。

## Web Admin Desktop Adaptation

- Web Admin 使用标准语义 HTML、桌面表单和表格交互作为可访问性基础，但不得退化为默认组件库皮肤。
- 最佳工作宽度为桌面和笔记本；宽屏增加表格/Inspector 的有效空间，不无限拉长普通表单行。
- 约 1050px 以下 Sidebar 收为 icon rail；约 820px 以下表单验证轨和任务 Inspector 堆叠为独立区块。
- 配置向导、危险确认和一次性 Secret 使用 Dialog 或独立步骤；不使用移动端 Bottom Sheet。
- 写操作在后端离线或会话失效时停止；保留最后快照并明确时间，不把缓存数据呈现为实时状态。
- 系统状态、表格选择、表单验证和危险操作必须在无 hover、无颜色和 reduced motion 情况下仍可理解。

### Confirmed Web Admin composition patterns

- `Overview` 使用“编辑式总体结论 → verdict strip → ledger rows → 需要处理轨 → 低强调配置摘要”。它不是可自由拼装的 KPI Card 网格。
- `Configuration` 使用“对象身份 → 分区介绍列 → 字段列 → verification rail → 粘性 action rail”。保存、测试、启用和设为默认保持独立状态与动作。
- `Operations` 使用“紧凑筛选 → 高密度表格/列表 → 附着式 Inspector”。Inspector 先给人类可读结论，再逐步披露锁定配置、错误和谱系。
- 列表 + 详情页面沿用任务诊断的主从关系；对象行通过左侧位置轨和 tonal wash 表达选择，不增加整页 Card 栅格。
- 页面标题区保持 28–40px 的呼吸空间；进入表单、列表或诊断后收紧到 44–52px 行高和 12–16px 组内间距。疏密变化是稳定的层级手段。

### Confirmed Web Admin interaction states

- Hover 只使用轻微 tonal wash；pressed 不产生位移；focus 使用清晰的 2px plum ring。任何主要操作都不能只在 hover 出现。
- 异步测试、保存与刷新在原位置反馈：保留已知内容，按钮进入局部处理中，结果通过字段附近状态与 `aria-live` 通知；不使用全页 loading 覆盖。
- 初次加载先显示真实页面骨架，不提前显示健康结论；单模块失败只替换对应区域，其他已加载内容继续可用。
- 空状态说明“为什么为空”和唯一下一步，不使用庆祝插画或营销文案。
- 未保存草稿、测试结果与活动配置必须同时可区分；测试失败不得使当前活动版本看起来失效。
- 后端离线使用顶端持久状态带，标注最后快照时间并停止写操作；恢复后在原页面刷新。
- 会话失效使用高层级重新认证 Dialog，保留目标路径与未提交输入；验证成功后回到原页面重新读取服务端状态。

### Confirmed dangerous and secret treatment

- 危险操作统一分为三段：影响与保留范围、显式确认、完成后的结果与恢复入口。不可恢复操作不得使用普通主按钮视觉。
- 需要降低误触的操作可要求输入短确认词；确认词只证明用户理解范围，不暗示操作可以撤销。
- App Token、API Key 与节点认证不显示伪造掩码值。现有 Secret 只显示“已配置”、更新时间与覆盖入口。
- 新 Secret 只在生成结果 Dialog 中显示一次；关闭前必须确认已安全保存。关闭后界面只保留标识、时间与状态。
- Admin Token 只用于登录和重新认证；网页不提供轮换或找回。丢失时的 SSH 恢复边界必须持续可见。

### Shared versus platform-specific boundary

- Android 与 Web Admin 共享：暖中性色、plum 品牌强调、清晰的排版层级、状态语义、单角收紧的形状家族、克制动效与不依赖颜色的反馈。
- Android 特有：摄影主导、Bottom Navigation、移动端全屏目的地、系统 Sheet、触控优先目标与平台返回行为。
- Web Admin 特有：固定分组 Sidebar、桌面路径顶栏、ledger、密集表格、右侧 Inspector、verification rail、粘性 action rail、键盘焦点和受控横向滚动。
- 跨平台统一不意味着组件结构相同；共享的是产品性格与语义，不是把任一平台界面机械缩放到另一平台。

## Governance

- 新页面先复用本文角色和原则，不为单页随意创建第二套圆角、色板或字体。
- 一次性页面差异保留在版本 UI Spec，不自动提升为全局 token。
- 若视觉要求与 Product Spec 冲突，Product Spec 优先；若实现限制要求改变已确认视觉方向，应先提出冲突而不是静默降级为默认 Material。
- V1.1 可复用素材、任务、结果、状态、对比和遮罩组件，但不应提前把会话、分支或层级概念暴露到 V1。
