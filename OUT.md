# RAG index contents

```
corpus dir : sample_docs/policy_corpus/  (8 .md files)
chunks     : 24  (en=12, ar=12)
embed model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
store      : in-memory numpy matrix (n_chunks x 384), rebuilt per process — NOT persisted

chunks per document:
  ar_prohibited_sectors            3
  ar_real_estate_ltv               3
  ar_sme_tenor                     3
  ar_watchlist_restructuring       3
  en_collateral_ltv                3
  en_credit_risk_ratios            3
  en_prohibited_activities         3
  en_sme_lending                   3
```

### `ar_prohibited_sectors#0`  ·  `ar`  ·  chars 0–348

> # الأنشطة المحظورة والمقيَّدة (وثيقة اصطناعية — ليست سياسة حقيقية للبنك) ## الأنشطة المحظورة لا يمنح البنك ائتماناً للمنشآت التي يكون نشاطها الرئيسي: القمار والمراهنات؛ أو إنتاج الأسلحة والذخائر أو الاتجار فيها؛ أو خدمات الصرافة أو تداول العملات دون ترخيص؛ أو إنتاج منتجات التبغ؛ أو استخراج الأسبستوس أو معالجته؛ أو أي نشاط مدرَج على قائمة العقوبات

### `ar_prohibited_sectors#1`  ·  `ar`  ·  chars 278–622

> ؛ أو استخراج الأسبستوس أو معالجته؛ أو أي نشاط مدرَج على قائمة العقوبات الوطنية. ## الأنشطة المقيَّدة (تتطلب مراجعة بيئية واجتماعية من المركز الرئيسي) يتطلب تمويل القطاعات التالية تقييماً للمخاطر البيئية والاجتماعية قبل الموافقة: إنتاج الأسمنت والجير؛ مدابغ الجلود ومعالجتها؛ مزارع الدواجن والماشية واسعة النطاق؛ أفران الطوب؛ والمحاجر. كما تتطلب

### `ar_prohibited_sectors#2`  ·  `ar`  ·  chars 552–868

> مزارع الدواجن والماشية واسعة النطاق؛ أفران الطوب؛ والمحاجر. كما تتطلب التسهيلات في هذه القطاعات التي تتجاوز 10,000,000 جنيه مصري زيارة ميدانية موثَّقة في ملف الائتمان. ## استثناء الزراعة يُسمح بالإقراض الزراعي وتصنيع الأغذية بالشكل المعتاد ولا يُعد نشاطاً مقيَّداً، شريطة وجود تصاريح استخدام المياه والصرف في الملف.

### `ar_real_estate_ltv#0`  ·  `ar`  ·  chars 0–348

> # قواعد الضمانات ونسبة التمويل إلى القيمة (وثيقة اصطناعية — ليست سياسة حقيقية للبنك) ## الضمان العقاري بالنسبة للعقارات التجارية المرهونة كضمان أساسي، يبلغ الحد الأقصى لنسبة التمويل إلى القيمة 70% من القيمة السوقية وفق تقييم مستقل حديث. وبالنسبة للعقارات السكنية يبلغ الحد الأقصى لنسبة التمويل إلى القيمة 80%. ويجب ألا يزيد عمر التقييم على 12 شهراً

### `ar_real_estate_ltv#1`  ·  `ar`  ·  chars 278–624

> ى لنسبة التمويل إلى القيمة 80%. ويجب ألا يزيد عمر التقييم على 12 شهراً عند السحب، وأن يُجريه مُقيِّم مُدرَج على قائمة المُقيِّمين المعتمدين لدى البنك. ## الضمان المنقول تُقبل الآلات والمعدات بحد أقصى 50% من صافي القيمة الدفترية أو 40% من قيمة البيع الجبري، أيهما أقل. ويُقبل المخزون المرهون برهن حيازي عائم بحد أقصى 40% من الأقل بين التكلفة وصافي

### `ar_real_estate_ltv#2`  ·  `ar`  ·  chars 554–898

> لمخزون المرهون برهن حيازي عائم بحد أقصى 40% من الأقل بين التكلفة وصافي القيمة البيعية، ويتطلب نسبة تغطية لا تقل عن 1.5 مرة من قيمة التسهيل القائم. ## الذمم المدينة تُقبل الذمم المدينة التجارية المُحالة بنسبة تصل إلى 80% من الفواتير المؤهلة التي يقل عمرها عن 90 يوماً. وتخضع الذمم المستحقة من مشترٍ واحد تتجاوز 25% من المحفظة المُحالة لخصم تركز.

### `ar_sme_tenor#0`  ·  `ar`  ·  chars 0–344

> # معايير إقراض الشركات الصغيرة والمتوسطة (وثيقة اصطناعية — ليست سياسة حقيقية للبنك) ## مدة التسهيل تُمنح تسهيلات رأس المال العامل للشركات الصغيرة والمتوسطة لمدة أقصاها 36 شهراً، قابلة للتجديد عند المراجعة السنوية. أما القروض لأجل لأغراض الإنفاق الرأسمالي فيجوز أن تصل مدتها إلى 84 شهراً، بما في ذلك فترة سماح لا تتجاوز 12 شهراً. وتُراجع تسهيلات

### `ar_sme_tenor#1`  ·  `ar`  ·  chars 274–613

> إلى 84 شهراً، بما في ذلك فترة سماح لا تتجاوز 12 شهراً. وتُراجع تسهيلات السحب على المكشوف والتسهيلات المتجددة مرة واحدة على الأقل كل 12 شهراً. ## حجم التسهيل يجب ألا يتجاوز إجمالي تعرض البنك لمجموعة عميل واحدة من الشركات الصغيرة والمتوسطة مبلغ 50,000,000 جنيه مصري دون تصعيد إلى لجنة الائتمان بالمركز الرئيسي. وتتطلب التسهيلات التي تزيد على

### `ar_sme_tenor#2`  ·  `ar`  ·  chars 543–887

> صعيد إلى لجنة الائتمان بالمركز الرئيسي. وتتطلب التسهيلات التي تزيد على 20,000,000 جنيه مصري قوائم مالية مدققة لسنتين ماليتين. ## الحد الأدنى للتسعير تُسعَّر تسهيلات الشركات الصغيرة والمتوسطة بحد أدنى قدره سعر البنك المركزي المصري مضافاً إليه 300 نقطة أساس. وأي تسعير دون هذا الحد يُعد استثناءً يتطلب موافقة لجنة الائتمان ويُوثَّق في ملف العميل.

### `ar_watchlist_restructuring#0`  ·  `ar`  ·  chars 0–341

> # قائمة المتابعة وإعادة الهيكلة (وثيقة اصطناعية — ليست سياسة حقيقية للبنك) ## مؤشرات الإنذار المبكر يُدرَج العميل على قائمة المتابعة عند تحقق أي من الحالات التالية: انخفاض نسبة تغطية خدمة الدين دون 1.10 مرة؛ أو تأخر السداد لأكثر من 30 يوماً؛ أو انخفاض نسبة تغطية الفوائد دون 1.5 مرة؛ أو تجاوز نسبة صافي الدين إلى الأرباح قبل الفوائد والضرائب

### `ar_watchlist_restructuring#1`  ·  `ar`  ·  chars 271–619

> دون 1.5 مرة؛ أو تجاوز نسبة صافي الدين إلى الأرباح قبل الفوائد والضرائب والإهلاك 4.0 مرات. ويُراجَع العملاء على قائمة المتابعة كل ربع سنة. ## إعادة الهيكلة لا يجوز إعادة هيكلة التسهيل إلا بموافقة لجنة الائتمان بالمركز الرئيسي، وبعد أن يقدم العميل خطة عمل محدَّثة. ولا تُخفَّض التصنيفات الائتمانية تلقائياً عند إعادة الهيكلة، لكن يجب رفع المخصصات وفق

### `ar_watchlist_restructuring#2`  ·  `ar`  ·  chars 549–847

> صنيفات الائتمانية تلقائياً عند إعادة الهيكلة، لكن يجب رفع المخصصات وفق تعليمات البنك المركزي المصري. ويظل التسهيل المُعاد هيكلته على قائمة المتابعة لمدة 12 شهراً على الأقل من تاريخ أول سداد منتظم. ## الإعفاءات أي انحراف عن هذه القواعد يُعد استثناءً صريحاً يجب توثيقه في ملف الائتمان مع بيان المبرر.

### `en_collateral_ltv#0`  ·  `en`  ·  chars 0–444

> # Collateral and Loan-to-Value Rules (SYNTHETIC — not real SCB policy) ## Real-estate collateral For commercial real estate pledged as primary collateral, the maximum loan-to-value ratio is 70% of the market value in a current independent valuation. For residential property the maximum loan-to-value ratio is 80%. Valuations must be no older than 12 months at drawdown and must be performed by a valuer on the bank's approved panel. ## Movable

### `en_collateral_ltv#1`  ·  `en`  ·  chars 354–802

> ths at drawdown and must be performed by a valuer on the bank's approved panel. ## Movable collateral Machinery and equipment are accepted at a maximum of 50% of net book value or 40% of forced- sale value, whichever is lower. Inventory pledged under a floating charge is accepted at a maximum of 40% of the lower of cost and net realisable value, and requires a minimum coverage ratio of 1.5 times the outstanding facility. ## Receivables Assigned

### `en_collateral_ltv#2`  ·  `en`  ·  chars 712–987

> es a minimum coverage ratio of 1.5 times the outstanding facility. ## Receivables Assigned trade receivables are accepted up to 80% of eligible invoices aged under 90 days. Receivables from a single buyer above 25% of the assigned pool are subject to a concentration haircut.

### `en_credit_risk_ratios#0`  ·  `en`  ·  chars 0–447

> # Credit Risk Ratio Thresholds (SYNTHETIC — not real SCB policy) ## Debt service coverage The minimum debt service coverage ratio (DSCR) for a new term facility is 1.25 times, measured on projected operating cash flow over scheduled principal and interest. Borrowers with a DSCR between 1.10 and 1.25 may be approved only with additional collateral or a shorter tenor, and the deviation must be justified in writing. ## Leverage Net debt to EBITDA

### `en_credit_risk_ratios#1`  ·  `en`  ·  chars 357–805

> rter tenor, and the deviation must be justified in writing. ## Leverage Net debt to EBITDA must not exceed 4.0 times at approval for a leveraged borrower, or 3.0 times for project finance. The current ratio (current assets over current liabilities) should be at least 1.1 times; a ratio below 1.0 is a red flag requiring Credit Committee attention. ## Interest cover The interest coverage ratio (EBIT over finance costs) must be at least 2.0 times.

### `en_credit_risk_ratios#2`  ·  `en`  ·  chars 715–943

> st cover The interest coverage ratio (EBIT over finance costs) must be at least 2.0 times. A borrower whose interest cover falls below 1.5 times during the life of the facility is placed on the watch list and reviewed quarterly.

### `en_prohibited_activities#0`  ·  `en`  ·  chars 0–438

> # Prohibited and Restricted Activities (SYNTHETIC — not real SCB policy) ## Prohibited The bank does not provide credit to businesses whose primary activity is: gambling or betting; production or trade of weapons and ammunition; unlicensed money-services or currency dealing; production of tobacco products; extraction or processing of asbestos; or any activity appearing on the national sanctions list. ## Restricted (require Head-Office

### `en_prohibited_activities#1`  ·  `en`  ·  chars 348–796

> any activity appearing on the national sanctions list. ## Restricted (require Head-Office Environmental & Social review) Credit to the following sectors requires an environmental and social risk assessment before approval: cement and lime production; tanneries and leather processing; large-scale poultry and livestock operations; brick kilns; and quarrying. Facilities in these sectors above EGP 10,000,000 also require a site visit documented in

### `en_prohibited_activities#2`  ·  `en`  ·  chars 706–988

> . Facilities in these sectors above EGP 10,000,000 also require a site visit documented in the credit file. ## Agriculture exception Standard agricultural and food-processing lending is permitted and is not a restricted activity, provided water-use and effluent permits are on file.

### `en_sme_lending#0`  ·  `en`  ·  chars 0–445

> # SME Lending Standards (SYNTHETIC — not real SCB policy) ## Tenor limits SME working-capital facilities are granted for a maximum tenor of 36 months, renewable on annual review. SME term loans for capital expenditure may run up to 84 months including a grace period that must not exceed 12 months. Overdraft and revolving facilities are uncommitted and reviewed at least once every 12 months. ## Facility size The total SME exposure to a single

### `en_sme_lending#1`  ·  `en`  ·  chars 355–796

> eviewed at least once every 12 months. ## Facility size The total SME exposure to a single obligor group must not exceed EGP 50,000,000 without escalation to the Head-Office Credit Committee. Facilities above EGP 20,000,000 require two years of audited financial statements. ## Pricing floor SME facilities are priced at a minimum of the Central Bank of Egypt corridor rate plus 300 basis points. Any pricing below this floor is an exception

### `en_sme_lending#2`  ·  `en`  ·  chars 706–873

> of Egypt corridor rate plus 300 basis points. Any pricing below this floor is an exception requiring Credit Committee approval and must be recorded in the credit file.
