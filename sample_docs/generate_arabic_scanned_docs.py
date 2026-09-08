"""
Generiše sintetičke SKENIRANE arapske PDF dokumente (image-only, bez text sloja) — za testiranje
OCR grane Document Ingestor-a (SPEC.md 3.1.1).

Za razliku od generate_sample_docs.py (reportlab, pravi tekst-PDF), ovde se svaka stranica prvo
iscrtava kao rasterizovana slika — PIL + arabic_reshaper/python-bidi za ispravno kontekstualno
oblikovanje arapskih glifova i RTL vizuelni redosled — pa se blago degradira (rotacija, blur, šum)
da liči na stvaran skener, i tek onda upakuje u PDF. pdfplumber/PyMuPDF ne mogu izvući tekst
direktno iz ovakvog PDF-a; mora OCR (isto ponašanje kao proposal 8.2 tabela: "before OCR" problemi
se hvataju pre ekstrakcije, sama ekstrakcija ide preko OCR grane).

Namerno koristi istu kompaniju i iste brojke kao clean engleski set (nile_delta_foods, FY2024) u
generate_sample_docs.py — priča je: isti klijent, ali ovaj put je dostavio skeniranu arapsku
kopiju umesto digitalnog engleskog dokumenta.

Layout i format konkretno modelovani po realnom javnom dokumentu (TMG Holding, standalone
financial statements FY2023, EGX-objavljen, revidiran EY/RSM Egypt) — dve stvari su preuzete
otud jer bitno menjaju realizam i OCR ponašanje naspram prve verzije:

1. **Brojevi u istočno-arapskim (Indic) ciframa** (١٢٣...), ne zapadnim (123...) — stvarni
   egipatski finansijski dokumenti tako ispisuju brojeve, ovo NIJE stilski izbor.
2. **Prave tabele sa linijama** (ne slobodno pozicioniran tekst u dve kolone) — vizuelne linije
   pomažu Tesseract-ovoj segmentaciji stranice mnogo više nego dva nezavisna desno-poravnata
   teksta bez granica (empirijski potvrđeno: prva verzija bez tabela je davala mnogo lošiji OCR
   na formskim redovima nego na brojčanim tabelama koje već jesu imale kolonsku strukturu).

Pokretanje:
    .venv/bin/python sample_docs/generate_arabic_scanned_docs.py
"""
from __future__ import annotations

import random
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).parent
FONT_DIR = Path("/usr/share/fonts/truetype/noto")
FONT_REGULAR = FONT_DIR / "NotoNaskhArabic-Regular.ttf"
FONT_BOLD = FONT_DIR / "NotoNaskhArabic-Bold.ttf"

PAGE_W, PAGE_H = 1654, 2339  # A4 @ 200 DPI — dovoljna rezolucija za pouzdan OCR
MARGIN = 100
RIGHT_X = PAGE_W - MARGIN

random.seed(7)

_WESTERN_TO_ARABIC_DIGITS = str.maketrans("0123456789,", "٠١٢٣٤٥٦٧٨٩٬")


def ar_num(value: str) -> str:
    """Zapadne cifre/zarez -> istočno-arapske (Indic) cifre + arapski separator hiljada —
    tako realni egipatski finansijski dokumenti ispisuju brojeve (vidi napomenu na vrhu fajla)."""
    return value.translate(_WESTERN_TO_ARABIC_DIGITS)


def shape(text: str) -> str:
    """Arapski tekst mora proći reshape (kontekstualni oblici slova) + bidi (vizuelni RTL
    redosled) pre iscrtavanja — PIL ne radi ovo samo od sebe, iscrtava slova nepovezano i
    obrnutim redosledom ako im se prosledi sirov (logical-order) string."""
    return get_display(arabic_reshaper.reshape(text))


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


class ArabicScanPage:
    """Iscrtava jednu 'skeniranu' stranicu — desno-poravnat (RTL) layout sa pravim tabelama."""

    def __init__(self) -> None:
        self.img = Image.new("L", (PAGE_W, PAGE_H), color=255)
        self.draw = ImageDraw.Draw(self.img)
        self.y = MARGIN

    def title(self, text: str, size: int = 44, gap: int = 24) -> None:
        font = _font(True, size)
        shaped = shape(text)
        w = self.draw.textlength(shaped, font=font)
        self.draw.text((RIGHT_X - w, self.y), shaped, font=font, fill=0)
        self.y += size + gap

    def line(self, text: str, size: int = 28, bold: bool = False, gap: int = 14, grey: bool = False) -> None:
        font = _font(bold, size)
        shaped = shape(text)
        w = self.draw.textlength(shaped, font=font)
        self.draw.text((RIGHT_X - w, self.y), shaped, font=font, fill=110 if grey else 0)
        self.y += size + gap

    def paragraph(self, text: str, size: int = 26, gap: int = 16, max_width: int | None = None) -> None:
        font = _font(False, size)
        max_width = max_width or (RIGHT_X - MARGIN)
        words = text.split(" ")
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            trial = " ".join(current + [word])
            if self.draw.textlength(shape(trial), font=font) > max_width and current:
                lines.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            lines.append(" ".join(current))
        for line in lines:
            shaped = shape(line)
            w = self.draw.textlength(shaped, font=font)
            self.draw.text((RIGHT_X - w, self.y), shaped, font=font, fill=0)
            self.y += size + 8
        self.y += gap - 8

    def table(
        self,
        rows: list[tuple[str, str]],
        header: tuple[str, str] | None = None,
        col_split: float = 0.60,
        row_height: int = 50,
        value_size: int = 25,
        label_size: int = 25,
        gap_after: int = 22,
    ) -> None:
        """Prava bordirana tabela: labela u desnoj koloni, vrednost u levoj — kao u realnim
        egipatskim finansijskim izveštajima (vidi napomenu na vrhu fajla). Vizuelne linije su
        namerne, ne kozmetičke — pomažu OCR segmentaciji."""
        left, right = MARGIN, RIGHT_X
        split_x = left + int((right - left) * col_split)
        n = len(rows) + (1 if header else 0)
        top = self.y

        for i in range(n + 1):
            y = top + i * row_height
            self.draw.line([(left, y), (right, y)], fill=0, width=3 if i in (0, n) else 1)
        bottom = top + n * row_height
        self.draw.line([(left, top), (left, bottom)], fill=0, width=3)
        self.draw.line([(right, top), (right, bottom)], fill=0, width=3)
        self.draw.line([(split_x, top), (split_x, bottom)], fill=0, width=1)

        def _cell(text: str, x0: int, x1: int, y0: int, bold: bool, size: int) -> None:
            font = _font(bold, size)
            shaped = shape(text)
            w = self.draw.textlength(shaped, font=font)
            cx = x1 - 14 - w
            cy = y0 + (row_height - size) // 2
            self.draw.text((cx, cy), shaped, font=font, fill=0)

        r = 0
        if header:
            _cell(header[0], split_x, right, top, True, label_size)
            _cell(header[1], left, split_x, top, True, value_size)
            r = 1
        for label, value in rows:
            y0 = top + r * row_height
            bold_row = label.strip().startswith("**") or value.strip().startswith("**")
            clean_label = label.replace("**", "")
            clean_value = value.replace("**", "")
            _cell(clean_label, split_x, right, y0, bold_row, label_size)
            _cell(clean_value, left, split_x, y0, bold_row, value_size)
            r += 1

        self.y = bottom + gap_after

    def table3(
        self,
        rows: list[tuple[str, str, str]],
        header: tuple[str, str, str],
        row_height: int = 46,
        label_size: int = 23,
        value_size: int = 23,
        gap_after: int = 22,
    ) -> None:
        """Komparativna bordirana tabela sa 3 kolone: opis (desno, najšira kolona), tekuća godina
        (sredina), prethodna godina (levo) — RTL konvencija realnih finansijskih izveštaja (bliža
        godina uz opis, starija dalje levo), vidi TMG referencu u napomeni na vrhu fajla."""
        left, right = MARGIN, RIGHT_X
        label_w = int((right - left) * 0.46)
        value_w = (right - left - label_w) // 2
        split1 = left + value_w
        split2 = split1 + value_w
        n = len(rows) + 1
        top = self.y

        for i in range(n + 1):
            y = top + i * row_height
            self.draw.line([(left, y), (right, y)], fill=0, width=3 if i in (0, n) else 1)
        bottom = top + n * row_height
        for x in (left, split1, split2, right):
            self.draw.line([(x, top), (x, bottom)], fill=0, width=3 if x in (left, right) else 1)

        def _cell(text: str, x0: int, x1: int, y0: int, bold: bool, size: int) -> None:
            font = _font(bold, size)
            shaped = shape(text)
            w = self.draw.textlength(shaped, font=font)
            cx = x1 - 12 - w
            cy = y0 + (row_height - size) // 2
            self.draw.text((cx, cy), shaped, font=font, fill=0)

        _cell(header[0], split2, right, top, True, label_size)
        _cell(header[1], split1, split2, top, True, value_size)
        _cell(header[2], left, split1, top, True, value_size)

        for i, (label, value_new, value_old) in enumerate(rows, start=1):
            y0 = top + i * row_height
            bold_row = (
                label.strip().startswith("**")
                or value_new.strip().startswith("**")
                or value_old.strip().startswith("**")
            )
            clean_label = label.replace("**", "")
            clean_new = value_new.replace("**", "")
            clean_old = value_old.replace("**", "")
            _cell(clean_label, split2, right, y0, bold_row, label_size)
            _cell(clean_new, split1, split2, y0, bold_row, value_size)
            _cell(clean_old, left, split1, y0, bold_row, value_size)

        self.y = bottom + gap_after

    def rule(self, gap: int = 16) -> None:
        self.y += 6
        self.draw.line([(MARGIN, self.y), (RIGHT_X, self.y)], fill=170, width=2)
        self.y += gap

    def spacer(self, h: int) -> None:
        self.y += h

    def degrade(self) -> Image.Image:
        """Blaga 'skener' degradacija — rotacija, blur, šum. Dovoljno realistično da testira
        proposal-ov rizik ('Arabic OCR accuracy on poor-quality documents', proposal str. 16),
        ali ne toliko agresivno da OCR postane neupotrebljiv."""
        img = self.img
        angle = random.uniform(-1.1, 1.1)
        img = img.rotate(angle, fillcolor=255, resample=Image.BICUBIC, expand=False)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.35))
        noise = Image.effect_noise(img.size, 14)
        img = Image.blend(img, noise, alpha=0.035)
        return img.convert("RGB")


def _save_scanned_pdf(pages: list[Image.Image], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    first, rest = pages[0], pages[1:]
    first.save(out_path, "PDF", resolution=200.0, save_all=True, append_images=rest)
    print(f"Generated {out_path.relative_to(OUT_DIR)} (skeniran, bez text sloja, {len(pages)} str.)")


# ---------------------------------------------------------------------------
# Sadržaj — Nile Delta Foods, ista FY2024 baza podataka kao u generate_sample_docs.py,
# ovoga puta kao arapski skenirani dokument (2 strane po dokumentu).
# ---------------------------------------------------------------------------

def generate_financial_statement_ar() -> None:
    p1 = ArabicScanPage()
    p1.title("شركة دلتا النيل للأغذية ش.م.م")
    p1.line("«شركة مساهمة مصرية»", size=24, grey=True)
    p1.line("القوائم المالية المستقلة للسنة المالية المنتهية في ٣١ ديسمبر ٢٠٢٤", size=28, bold=True)
    p1.spacer(4)
    p1.line(
        "أُعدت وفقاً لمعايير المحاسبة المصرية والمعايير الدولية لإعداد التقارير المالية، وروجعت "
        "من قبل حسن علام وشركاه «محاسبون قانونيون معتمدون»، مسجلة لدى الهيئة العامة للرقابة المالية",
        size=20, grey=True,
    )
    p1.line("جميع المبالغ بالجنيه المصري ما لم يُذكر خلاف ذلك", size=20, grey=True)
    p1.line("السجل التجاري رقم: ١٨٤٧٢٩ «القاهرة»    البطاقة الضريبية: ٥٤٧ ٨٩١ ٢٠٣", size=20, grey=True)
    p1.line("«وثيقة اختبار اصطناعية، ليست شركة حقيقية، تقرير مراقب الحسابات الكامل غير مرفق في هذه العينة»", size=18, grey=True)
    p1.rule()

    p1.line("قائمة المركز المالي كما في ٣١ ديسمبر ٢٠٢٤", size=30, bold=True)
    p1.spacer(8)
    p1.table(
        header=("الأصول", "جنيه مصري"),
        rows=[
            ("النقدية وما في حكمها ﴾٩﴿", ar_num("11,200,000")),
            ("المدينون وأرصدة مدينة أخرى ﴾٦﴿", ar_num("25,400,000")),
            ("المخزون ﴾٥﴿", ar_num("34,600,000")),
            ("الممتلكات والآلات والمعدات، صافي ﴾٣﴿", ar_num("48,900,000")),
            ("**إجمالي الأصول**", "**" + ar_num("124,800,000") + "**"),
        ],
    )
    p1.table(
        header=("حقوق الملكية والالتزامات", "جنيه مصري"),
        rows=[
            ("الدائنون وأرصدة دائنة أخرى ﴾١٠﴿", ar_num("21,300,000")),
            ("قروض قصيرة الأجل ﴾١١﴿", ar_num("16,800,000")),
            ("قروض طويلة الأجل ﴾١١﴿", ar_num("24,100,000")),
            ("**إجمالي الالتزامات**", "**" + ar_num("65,200,000") + "**"),
            ("**إجمالي حقوق الملكية**", "**" + ar_num("59,600,000") + "**"),
        ],
    )

    p2 = ArabicScanPage()
    p2.line("شركة دلتا النيل للأغذية ش.م.م، القوائم المالية المستقلة، ٣١ ديسمبر ٢٠٢٤ «تابع»", size=22, bold=True)
    p2.rule()

    p2.line("قائمة الأرباح أو الخسائر عن السنة المنتهية في ٣١ ديسمبر ٢٠٢٤", size=30, bold=True)
    p2.spacer(8)
    p2.table(
        header=("البند", "جنيه مصري"),
        rows=[
            ("الإيرادات ﴾٤﴿", ar_num("208,300,000")),
            ("تكلفة المبيعات", ar_num("141,600,000")),
            ("مجمل الربح", ar_num("66,700,000")),
            ("مصروفات عمومية وإدارية", ar_num("42,500,000")),
            ("الربح التشغيلي", ar_num("24,200,000")),
            ("تكاليف التمويل ﴾١١﴿", ar_num("5,400,000")),
            ("**صافي ربح السنة**", "**" + ar_num("15,800,000") + "**"),
        ],
    )

    p2.line("الإيضاحات المتممة للقوائم المالية «مستخرج مختصر»", size=28, bold=True)
    p2.spacer(6)
    p2.line("إيضاح ﴾٥﴿: المخزون", size=24, bold=True)
    p2.paragraph(
        "يتكون المخزون بصورة أساسية من المواد الخام والمنتجات تامة الصنع بمصنع الشركة بمدينة ٦ "
        "أكتوبر، ويُقيّم بالتكلفة أو صافي القيمة البيعية أيهما أقل، وفقاً للسياسة المحاسبية "
        "الموضحة في إيضاح السياسات المحاسبية الهامة."
    )
    p2.spacer(6)
    p2.line("إيضاح ﴾١١﴿: القروض والتسهيلات المصرفية القائمة", size=24, bold=True)
    p2.paragraph(
        "لدى الشركة تسهيل تشغيلي متجدد من بنك قناة السويس ارتفع إلى " + ar_num("18,000,000") +
        " جنيه مصري في الربع الثاني من عام ٢٠٢٤ «بنسبة استخدام " + ar_num("65") + "٪». خط الاعتماد "
        "المستندي لدى البنك الأهلي المصري دون تغيير عند " + ar_num("8,000,000") + " جنيه مصري. تم "
        "توقيع خط تمويل معدات جديد بقيمة " + ar_num("5,000,000") +
        " جنيه مصري مع بنك مصر في الربع الرابع من ٢٠٢٤ لتحديث خط الإنتاج."
    )
    p2.line(
        "ملاحظة: يتم إبلاغ إجمالي التعرض المصرفي للبنك المركزي المصري ضمن إطار مركز التجميع الائتماني.",
        size=18, grey=True,
    )

    _save_scanned_pdf(
        [p1.degrade(), p2.degrade()],
        OUT_DIR / "nile_delta_foods" / "nile_delta_foods_financial_statements_fy2024_arabic_scan.pdf",
    )


def generate_loan_application_ar() -> None:
    p1 = ArabicScanPage()
    p1.title("طلب تسهيل ائتماني للشركات")
    p1.line("بنك قناة السويس، قطاع الخدمات المصرفية للشركات", size=28, bold=True)
    p1.line("نموذج رقم ٠١ «مراجعة ٢٠٢٣»    للاستخدام الداخلي، مراجعة لجنة الائتمان", size=20, grey=True)
    p1.line("«وثيقة اختبار اصطناعية، ليست شركة أو بنكاً حقيقياً»", size=18, grey=True)
    p1.rule()

    p1.line("القسم أ: بيانات مقدم الطلب", size=28, bold=True)
    p1.spacer(6)
    p1.table(rows=[
        ("الاسم بالعربية", "شركة دلتا النيل للأغذية ش.م.م"),
        ("رقم السجل التجاري", ar_num("184729") + " «القاهرة»"),
        ("البطاقة الضريبية", ar_num("547 891 203")),
        ("النشاط", "الصناعات الغذائية والتوزيع"),
        ("المحافظة", "مدينة ٦ أكتوبر، الجيزة"),
        ("سنوات النشاط", ar_num("18")),
        ("العلاقة مع بنك قناة السويس منذ", ar_num("2014")),
    ])

    p1.line("القسم ب: التسهيل المطلوب", size=28, bold=True)
    p1.spacer(6)
    p1.table(rows=[
        ("المبلغ المطلوب", "**" + ar_num("25,000,000") + " جنيه مصري**"),
        ("نوع التسهيل", "قرض لأجل، ٧ سنوات"),
        ("جدول السداد", "أقساط ربع سنوية متساوية"),
    ])
    p1.paragraph("الغرض من التمويل: توسعة سعة التخزين المبرد بمصنع ٦ أكتوبر ورأس المال العامل الموسمي.")

    p2 = ArabicScanPage()
    p2.line("طلب تسهيل ائتماني للشركات، شركة دلتا النيل للأغذية «تابع»", size=22, bold=True)
    p2.rule()

    p2.line("القسم ج: الضمانات المقدمة", size=28, bold=True)
    p2.spacer(4)
    p2.paragraph(
        "رهن من الدرجة الأولى على منشأة الإنتاج بالقطعة ١٤، المنطقة الصناعية، ٦ أكتوبر «بتقييم "
        "مستقل بقيمة " + ar_num("42,000,000") + " جنيه مصري من قبل المقيّم المعتمد، الشركة "
        "المصرية للتقييم العقاري، بتاريخ يناير ٢٠٢٥»؛ حوالة حقوق من أكبر ٣ عملاء بالتجزئة؛ كفالة "
        "من الشركة الأم، شركة دلتا النيل القابضة ش.م.م؛ كفالة شخصية من السيد أحمد حسن فاروق "
        "«العضو المنتدب»."
    )
    p2.rule()

    p2.line("القسم د: التسهيلات المصرفية القائمة «بحسب إقرار مقدم الطلب»", size=26, bold=True)
    p2.spacer(6)
    p2.table(rows=[
        ("تسهيل تشغيلي، بنك قناة السويس", ar_num("18,000,000") + " «استخدام ٦٥٪»"),
        ("اعتماد مستندي، البنك الأهلي المصري", ar_num("8,000,000")),
        ("تمويل معدات، بنك مصر", ar_num("5,000,000") + " «الربع الرابع ٢٠٢٤»"),
    ])
    p2.line("تقرير مركز التجميع الائتماني بتاريخ فبراير ٢٠٢٥ مرفق.", size=20, grey=True)
    p2.spacer(10)
    p2.line("القسم هـ: إقرار مقدم الطلب", size=26, bold=True)
    p2.paragraph(
        "يقر مقدم الطلب بأن جميع البيانات الواردة أعلاه صحيحة ومكتملة، وأنه لا توجد تسهيلات "
        "مصرفية أخرى غير مفصح عنها لدى أي بنك مرخص آخر."
    )

    _save_scanned_pdf(
        [p1.degrade(), p2.degrade()],
        OUT_DIR / "nile_delta_foods" / "nile_delta_foods_loan_application_arabic_scan.pdf",
    )


# ---------------------------------------------------------------------------
# Misr Pharma Distribution — bogatiji test dokument: DVE godine uporedo (FY2023 vs FY2024, kao u
# realnim finansijskim izveštajima — vidi TMG referencu na vrhu fajla), više red stavki i više
# beleški. Brojevi su preuzeti direktno iz EGYPTIAN_CASES u generate_sample_docs.py (isti izvor
# istine kao clean engleski set za ovu kompaniju), ne izmišljeni za ovaj dokument.
# ---------------------------------------------------------------------------

def generate_misr_pharma_financial_statement_ar() -> None:
    p1 = ArabicScanPage()
    p1.title("شركة مصر لتجارة الأدوية ش.م.م")
    p1.line("«شركة مساهمة مصرية»", size=24, grey=True)
    p1.line("القوائم المالية المستقلة للسنة المالية المنتهية في ٣١ ديسمبر ٢٠٢٤", size=27, bold=True)
    p1.line("«مع أرقام المقارنة للسنة المالية ٢٠٢٣»", size=22, grey=True)
    p1.spacer(4)
    p1.line(
        "أُعدت وفقاً لمعايير المحاسبة المصرية والمعايير الدولية لإعداد التقارير المالية، وروجعت "
        "من قبل كي بي إم جي مصر «محاسبون قانونيون معتمدون»، مسجلة لدى الهيئة العامة للرقابة المالية",
        size=19, grey=True,
    )
    p1.line("جميع المبالغ بالجنيه المصري ما لم يُذكر خلاف ذلك", size=19, grey=True)
    p1.line("السجل التجاري رقم: 334512 «القاهرة»    البطاقة الضريبية: 891 567 234", size=19, grey=True)
    p1.line("النشاط: تجارة وتوزيع الأدوية بالجملة    المحافظة: مدينة نصر، القاهرة", size=19, grey=True)
    p1.line("«وثيقة اختبار اصطناعية، ليست شركة حقيقية»", size=18, grey=True)
    p1.rule()

    p1.line("قائمة المركز المالي كما في ٣١ ديسمبر", size=29, bold=True)
    p1.spacer(6)
    p1.table3(
        header=("الأصول", "٢٠٢٤", "٢٠٢٣"),
        rows=[
            ("النقدية وما في حكمها ﴾٩﴿", ar_num("8,100,000"), ar_num("6,800,000")),
            ("المدينون وأرصدة مدينة أخرى ﴾٦﴿", ar_num("44,800,000"), ar_num("41,500,000")),
            ("المخزون ﴾٥﴿", ar_num("56,700,000"), ar_num("52,300,000")),
            ("الممتلكات والآلات والمعدات، صافي ﴾٣﴿", ar_num("15,600,000"), ar_num("14,200,000")),
            ("**إجمالي الأصول**", "**" + ar_num("129,400,000") + "**", "**" + ar_num("118,900,000") + "**"),
        ],
    )
    p1.table3(
        header=("حقوق الملكية والالتزامات", "٢٠٢٤", "٢٠٢٣"),
        rows=[
            ("الدائنون وأرصدة دائنة أخرى ﴾١٠﴿", ar_num("41,200,000"), ar_num("38,600,000")),
            ("قروض قصيرة الأجل ﴾١١﴿", ar_num("31,500,000"), ar_num("28,400,000")),
            ("قروض طويلة الأجل ﴾١١﴿", ar_num("7,800,000"), ar_num("6,500,000")),
            ("**إجمالي الالتزامات**", "**" + ar_num("83,500,000") + "**", "**" + ar_num("76,500,000") + "**"),
            ("**إجمالي حقوق الملكية**", "**" + ar_num("45,900,000") + "**", "**" + ar_num("42,400,000") + "**"),
        ],
    )

    p2 = ArabicScanPage()
    p2.line("شركة مصر لتجارة الأدوية ش.م.م، القوائم المالية المستقلة، ٣١ ديسمبر ٢٠٢٤ «تابع»", size=21, bold=True)
    p2.rule()

    p2.line("قائمة الأرباح أو الخسائر عن السنة المنتهية في ٣١ ديسمبر", size=29, bold=True)
    p2.spacer(6)
    p2.table3(
        header=("البند", "٢٠٢٤", "٢٠٢٣"),
        rows=[
            ("الإيرادات ﴾٤﴿", ar_num("341,200,000"), ar_num("312,600,000")),
            ("تكلفة المبيعات", ar_num("291,800,000"), ar_num("268,400,000")),
            ("مجمل الربح", ar_num("49,400,000"), ar_num("44,200,000")),
            ("مصروفات عمومية وإدارية", ar_num("31,400,000"), ar_num("28,900,000")),
            ("الربح التشغيلي", ar_num("18,000,000"), ar_num("15,300,000")),
            ("تكاليف التمويل ﴾١١﴿", ar_num("5,800,000"), ar_num("5,100,000")),
            ("**صافي ربح السنة**", "**" + ar_num("9,600,000") + "**", "**" + ar_num("7,200,000") + "**"),
        ],
    )

    p2.line("إيضاح ﴾٣﴿: الممتلكات والآلات والمعدات", size=23, bold=True)
    p2.spacer(4)
    p2.paragraph(
        "تتكون هذه الفئة بصورة أساسية من مخزن التوزيع الرئيسي بمدينة نصر وسيارات التوزيع المبرد "
        "الخاصة بنقل الأدوية الحساسة لدرجة الحرارة. يُحتسب الإهلاك بطريقة القسط الثابت على مدى "
        "الأعمار الإنتاجية المقدرة للأصول."
    )
    p2.spacer(6)
    p2.line("إيضاح ﴾٥﴿: المخزون", size=23, bold=True)
    p2.paragraph(
        "يتكون المخزون من أدوية مستوردة ومحلية معدة لإعادة البيع، ويخضع لمتابعة دورية لتواريخ "
        "الصلاحية. يُقيّم بالتكلفة أو صافي القيمة البيعية أيهما أقل، مع مخصص للأصناف قريبة "
        "الانتهاء وفقاً للسياسة المحاسبية الموضحة في إيضاح السياسات المحاسبية الهامة."
    )

    p3 = ArabicScanPage()
    p3.line("شركة مصر لتجارة الأدوية ش.م.م، الإيضاحات المتممة «تابع»", size=21, bold=True)
    p3.rule()

    p3.line("إيضاح ﴾٦﴿: المدينون وأرصدة مدينة أخرى", size=23, bold=True)
    p3.spacer(4)
    p3.paragraph(
        "تتمثل المدينون بصورة أساسية في أرصدة مستحقة من الصيدليات ومستشفيات القطاع الخاص، بمتوسط "
        "فترة تحصيل حوالي ٦٠ يوماً. تحتفظ الشركة بمخصص هبوط قيمة يُراجع في نهاية كل فترة مالية "
        "وفقاً لأعمار الأرصدة."
    )
    p3.spacer(6)
    p3.line("إيضاح ﴾١١﴿: القروض والتسهيلات المصرفية القائمة", size=23, bold=True)
    p3.spacer(4)
    p3.paragraph(
        "٢٠٢٣: لدى الشركة تسهيل تمويل مخزون بقيمة " + ar_num("30,000,000") +
        " جنيه مصري لدى بنك قناة السويس «بنسبة استخدام ٨١٪»، بالإضافة إلى تسهيل سحب على المكشوف "
        "بقيمة " + ar_num("5,000,000") + " جنيه مصري لدى البنك العربي الأفريقي الدولي لتغطية دورة "
        "الرواتب."
    )
    p3.paragraph(
        "٢٠٢٤: ارتفع تسهيل تمويل المخزون لدى بنك قناة السويس إلى " + ar_num("35,000,000") +
        " جنيه مصري «بنسبة استخدام ٧٦٪». تم سداد وإغلاق تسهيل السحب على المكشوف لدى البنك العربي "
        "الأفريقي الدولي بالكامل في الربع الثاني من ٢٠٢٤، ولم يتم الحصول على أي تسهيلات خارجية "
        "جديدة خلال العام."
    )
    p3.line(
        "ملاحظة: يتم إبلاغ إجمالي التعرض المصرفي للبنك المركزي المصري ضمن إطار مركز التجميع الائتماني.",
        size=18, grey=True,
    )

    _save_scanned_pdf(
        [p1.degrade(), p2.degrade(), p3.degrade()],
        OUT_DIR / "misr_pharma" / "misr_pharma_financial_statements_fy2024_arabic_scan.pdf",
    )


def generate_misr_pharma_loan_application_ar() -> None:
    p1 = ArabicScanPage()
    p1.title("طلب تسهيل ائتماني للشركات")
    p1.line("بنك قناة السويس، قطاع الخدمات المصرفية للشركات", size=28, bold=True)
    p1.line("نموذج رقم ٠١ «مراجعة ٢٠٢٣»    للاستخدام الداخلي، مراجعة لجنة الائتمان", size=20, grey=True)
    p1.line("«وثيقة اختبار اصطناعية، ليست شركة أو بنكاً حقيقياً»", size=18, grey=True)
    p1.rule()

    p1.line("القسم أ: بيانات مقدم الطلب", size=28, bold=True)
    p1.spacer(6)
    p1.table(rows=[
        ("الاسم بالعربية", "شركة مصر لتجارة الأدوية ش.م.م"),
        ("رقم السجل التجاري", ar_num("334512") + " «القاهرة»"),
        ("البطاقة الضريبية", ar_num("891 567 234")),
        ("النشاط", "تجارة وتوزيع الأدوية بالجملة"),
        ("المحافظة", "مدينة نصر، القاهرة"),
        ("سنوات النشاط", ar_num("15")),
        ("العلاقة مع بنك قناة السويس منذ", ar_num("2016")),
    ])

    p1.line("القسم ب: التسهيل المطلوب", size=28, bold=True)
    p1.spacer(6)
    p1.table(rows=[
        ("المبلغ المطلوب", "**" + ar_num("20,000,000") + " جنيه مصري**"),
        ("نوع التسهيل", "تمويل مخزون متجدد، مدته سنتان"),
        ("جدول السداد", "متجدد، مراجعة سنوية لحد التسهيل"),
    ])
    p1.paragraph(
        "الغرض من التمويل: تخزين أدوية مستوردة لعلاج الأورام والأمراض المزمنة استعداداً لموسم "
        "مناقصات وزارة الصحة."
    )

    p2 = ArabicScanPage()
    p2.line("طلب تسهيل ائتماني للشركات، شركة مصر لتجارة الأدوية «تابع»", size=22, bold=True)
    p2.rule()

    p2.line("القسم ج: الضمانات المقدمة", size=28, bold=True)
    p2.spacer(4)
    p2.paragraph(
        "رهن عائم على مخزون الأدوية «بحد أدنى لنسبة التغطية ١.٥ ضعف قيمة التسهيل»؛ مخزن بالقطعة "
        "٢٢، المنطقة الصناعية، العاشر من رمضان «بقيمة تقديرية " + ar_num("18,000,000") +
        " جنيه مصري»؛ كفالة شخصية من الدكتورة ياسمين المصري «الرئيس التنفيذي» والسيد طارق عبد "
        "الرحمن «المدير المالي»."
    )
    p2.rule()

    p2.line("القسم د: التسهيلات المصرفية القائمة «بحسب إقرار مقدم الطلب»", size=25, bold=True)
    p2.spacer(6)
    p2.table(rows=[
        ("تمويل مخزون، بنك قناة السويس", ar_num("35,000,000") + " «استخدام ٧٦٪»"),
        ("سحب على المكشوف، البنك العربي الأفريقي", "مسدد ومغلق «الربع الثاني ٢٠٢٤»"),
    ])
    p2.line("تقرير مركز التجميع الائتماني بتاريخ فبراير ٢٠٢٥: لا توجد تسهيلات أخرى.", size=19, grey=True)
    p2.spacer(10)

    p2.line("القسم هـ: ملخص المؤشرات المالية «للمراجعة الداخلية»", size=25, bold=True)
    p2.spacer(6)
    p2.table3(
        header=("المؤشر", "٢٠٢٤", "٢٠٢٣"),
        rows=[
            ("نسبة التداول «الأصول المتداولة إلى الالتزامات المتداولة»", "١.٤٨", "١.٣٥"),
            ("نسبة الدين إلى حقوق الملكية", "١.٨٢", "١.٨٠"),
            ("نسبة تغطية فوائد التمويل", "٤.١٠", "٣.٩٠"),
        ],
    )

    p2.line("القسم و: إقرار مقدم الطلب", size=25, bold=True)
    p2.paragraph(
        "يقر مقدم الطلب بأن جميع البيانات الواردة أعلاه صحيحة ومكتملة، وأنه لا توجد تسهيلات "
        "مصرفية أخرى غير مفصح عنها لدى أي بنك مرخص آخر."
    )

    _save_scanned_pdf(
        [p1.degrade(), p2.degrade()],
        OUT_DIR / "misr_pharma" / "misr_pharma_loan_application_arabic_scan.pdf",
    )


def main() -> None:
    generate_financial_statement_ar()
    generate_loan_application_ar()
    generate_misr_pharma_financial_statement_ar()
    generate_misr_pharma_loan_application_ar()


if __name__ == "__main__":
    main()
