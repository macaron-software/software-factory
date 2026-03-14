# i18n & RTL — Deep Skill
# 40 Languages + RTL Support

## WHEN TO ACTIVATE
Creating any user-facing text, templates, forms, dates, numbers, currency,
or layout. Always internationalize from day one — retrofitting is 10x harder.

## 40 SUPPORTED LANGUAGES
### LTR Languages (34)
| Code | Language | Region | Script |
|------|----------|--------|--------|
| en | English | Global | Latin |
| fr | French | France/Africa/Canada | Latin |
| es | Spanish | Spain/LatAm | Latin |
| pt | Portuguese | Portugal/Brazil | Latin |
| de | German | DACH | Latin |
| it | Italian | Italy | Latin |
| nl | Dutch | Netherlands/Belgium | Latin |
| pl | Polish | Poland | Latin |
| ro | Romanian | Romania | Latin |
| cs | Czech | Czech Republic | Latin |
| sk | Slovak | Slovakia | Latin |
| hu | Hungarian | Hungary | Latin |
| hr | Croatian | Croatia | Latin |
| bg | Bulgarian | Bulgaria | Cyrillic |
| uk | Ukrainian | Ukraine | Cyrillic |
| ru | Russian | Russia | Cyrillic |
| el | Greek | Greece | Greek |
| tr | Turkish | Turkey | Latin |
| vi | Vietnamese | Vietnam | Latin |
| th | Thai | Thailand | Thai |
| ko | Korean | Korea | Hangul |
| ja | Japanese | Japan | Kanji/Kana |
| zh-CN | Chinese Simplified | China | Hanzi |
| zh-TW | Chinese Traditional | Taiwan | Hanzi |
| id | Indonesian | Indonesia | Latin |
| ms | Malay | Malaysia | Latin |
| tl | Filipino | Philippines | Latin |
| hi | Hindi | India | Devanagari |
| bn | Bengali | Bangladesh/India | Bengali |
| sw | Swahili | East Africa | Latin |
| am | Amharic | Ethiopia | Ethiopic |
| ha | Hausa | West Africa | Latin |
| yo | Yoruba | Nigeria | Latin |
| ig | Igbo | Nigeria | Latin |

### RTL Languages (6)
| Code | Language | Region | Script |
|------|----------|--------|--------|
| ar | Arabic | MENA | Arabic |
| he | Hebrew | Israel | Hebrew |
| fa | Persian/Farsi | Iran | Arabic |
| ur | Urdu | Pakistan/India | Arabic |
| ps | Pashto | Afghanistan | Arabic |
| ku | Kurdish (Sorani) | Iraq/Iran | Arabic |

## RTL IMPLEMENTATION
```html
<html dir="auto" lang="{{ locale }}">
<!-- Or set dynamically: -->
<html dir="{{ 'rtl' if locale in RTL_LOCALES else 'ltr' }}" lang="{{ locale }}">
```

### CSS for RTL
```css
/* Use logical properties — works for both LTR and RTL */
.card {
  margin-inline-start: 1rem;   /* NOT margin-left */
  padding-inline-end: 0.5rem;  /* NOT padding-right */
  border-inline-start: 2px solid var(--purple);  /* NOT border-left */
  text-align: start;           /* NOT text-align: left */
  float: inline-start;         /* NOT float: left */
}

/* Flexbox auto-reverses with dir="rtl" — no changes needed */
.nav { display: flex; }

/* Icons that indicate direction need flipping */
[dir="rtl"] .icon-arrow-right { transform: scaleX(-1); }
[dir="rtl"] .icon-chevron-right { transform: scaleX(-1); }
/* BUT: don't flip checkmarks, close, add, media controls */
```

### Logical Properties Mapping
| Physical | Logical | Adapts to RTL |
|----------|---------|---------------|
| margin-left | margin-inline-start | Yes |
| margin-right | margin-inline-end | Yes |
| padding-left | padding-inline-start | Yes |
| padding-right | padding-inline-end | Yes |
| border-left | border-inline-start | Yes |
| text-align: left | text-align: start | Yes |
| left: 0 | inset-inline-start: 0 | Yes |
| right: 0 | inset-inline-end: 0 | Yes |
| float: left | float: inline-start | Yes |
| width | inline-size | (block axis) |
| height | block-size | (block axis) |

## TRANSLATION FRAMEWORK
### Key Extraction
```python
# platform/i18n/
from i18n import t, set_locale

# In templates:
{{ t('dashboard.title') }}
{{ t('mission.phase_count', count=phases) }}  # pluralization
{{ t('agent.score', score=score, name=name) }}  # interpolation

# In Python:
message = t('error.not_found', resource=resource_name)
```

### File Structure
```
platform/i18n/
  locales/
    en.json     # English (source of truth)
    fr.json     # French
    ar.json     # Arabic (RTL)
    ...40 files
  __init__.py   # t(), set_locale(), get_locale()
  plurals.py    # CLDR plural rules per language
  formats.py    # Date/number/currency formatting
```

### Translation Key Conventions
```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "confirm": "Confirm",
    "loading": "Loading...",
    "error": "An error occurred",
    "success": "Success"
  },
  "dashboard": {
    "title": "Dashboard",
    "agents_count": "{count, plural, one {# agent} other {# agents}}"
  },
  "mission": {
    "status": {
      "running": "Running",
      "completed": "Completed",
      "failed": "Failed"
    }
  }
}
```

## DATE & NUMBER FORMATTING
```python
# Use ICU/CLDR, never manual formatting
from babel.dates import format_datetime
from babel.numbers import format_decimal, format_currency

format_datetime(dt, locale='fr_FR')  # "14 mars 2026 15:26"
format_datetime(dt, locale='ar')     # "١٤ مارس ٢٠٢٦ ١٥:٢٦"
format_decimal(1234.56, locale='de') # "1.234,56"
format_currency(99.99, 'EUR', locale='fr') # "99,99 €"
```

## EMPATHETIC MESSAGES PER CULTURE
```json
{
  "en": {
    "retry_message": "Something went wrong. Let's try again.",
    "offline_message": "You seem to be offline. We'll save your work and sync when you're back.",
    "error_empathy": "We're sorry about this. Our team is looking into it."
  },
  "fr": {
    "retry_message": "Une erreur s'est produite. Réessayons ensemble.",
    "offline_message": "Vous semblez hors ligne. Votre travail est sauvegardé et sera synchronisé au retour.",
    "error_empathy": "Nous sommes désolés. Notre équipe travaille sur ce problème."
  },
  "ja": {
    "retry_message": "問題が発生しました。もう一度お試しください。",
    "offline_message": "オフラインのようです。作業は保存され、接続復帰時に同期されます。",
    "error_empathy": "ご不便をおかけして申し訳ございません。チームが対応中です。"
  },
  "ar": {
    "retry_message": "حدث خطأ ما. دعنا نحاول مرة أخرى.",
    "offline_message": "يبدو أنك غير متصل. سيتم حفظ عملك ومزامنته عند عودتك.",
    "error_empathy": "نعتذر عن هذا الخطأ. فريقنا يعمل على حله."
  }
}
```

## RULES
1. NEVER hardcode text strings in templates or code — use i18n keys
2. NEVER concatenate translated strings — use interpolation
3. NEVER assume LTR layout — use CSS logical properties
4. NEVER assume Latin script — test with CJK, Arabic, Devanagari
5. NEVER assume date/number formats — use locale-aware formatting
6. Support pluralization via CLDR rules (Arabic has 6 plural forms!)
7. Allow text expansion (German ~30% longer than English)
8. Test RTL layout with Arabic/Hebrew to catch mirroring issues
9. Store translations in JSON, not code — enable external translation
10. Include context comments for translators in source files
