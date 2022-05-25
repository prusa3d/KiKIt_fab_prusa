# Nastavení projektu

- KiCAD projekt musí obsahovat textovou proměnnou `ID`, což je ID DMC.
- KiCAD project musí obsahovat textovou proměnnou `TECHNOLOGY_PARAMS`, která
  specifikuje název sady designových pravidel. Dostupná pravidla jsou k nalazení
  ve složce [designRules](../prusaman/resources/designRules/). Uvádí se bez
  přípony `.json`.
- Jak schéma, tak i deska musí obsahovat shodné nastavení revize.

Ukázkové projekty jsou k nalezení v adresáři [examples](examples).


## Filtrování BOMu

Nakupování/osazování se řídí pomocí pole `pnb` u značek:
    - `#` – neosazuji, nakupuji
    - `dnf` – *ne*osazuji, *ne*nakupuji
    - `` (prázdné pole) – osazuji, nakupuji

Zároveň se ignorují symboly, jejichž reference začíná na jedno z:
`#` (symboly napájení), `M`, `NT`, `G`.

## Specifikace panelu

Panel je možné specifikovat pomocí jednoho ze třech nástrojů:
- Použije se [KiKit](https://github.com/yaqwsx/KiKit) pro generování
  panelu. Konfigurace se očekává v souboru `kikit.json`
- Použije se uživatelem dodaný **skript** pro výrobu panelu. Skript se
  musí jmenovat `panel.sh`. Očekává se, že skript dostane dva argumenty: `skript
  <cesta_ke_zdrojové_desce> <cesta_k_výstupu>`. Tato možnost je vhodná, pokud si
  např. uživatel napsal vlastní panelizační skript pomocí KiKitu (protože panel
  není možné naspecifikovat jen z CLI)
- Panel je manuálně nakreslen. Očekává se, že existuje jako
  `panel/panel.kicad_pcb`

## Jak specifikovat panely dle Prusa Guide v KiKitu:

- jako frame použít `plugin`, `code` je `prusaman.Frame` a jako argument dostane
  požadovanou utilizovanou výšku panelu (jedno z 143mm, 154mm, 196mm)
- pro tvorbu tooling holes použít `plugin`, `code` je `prusaman.Tooling`.
  Tooling plugin nemá žádné argumenty.
- nezapomeň uvést v sekci `post`: `origin: bl` a v sekci `page`: `anchor: bl` a
  `posx: 0mm` a `posy: 0mm`.

K dispozici je [příklad](examples/simple_pnb/kikit.json).

## Šablony a argumenty

V momentě, kdy specifikujete výrobní proces, existují nějaké neznámé (např.
rozměry panelu, datum generování apod.) Pro tyto účely je možné používat
proměnné v šablonách readme a v konfiguračním YAML souboru. Proměnné se
specifikují jako v Pythonu – tj. do složených závorek, např: `Dnes je {date}`.

Podporovány jsou následující proměnné:
- `size` – velikost desky k níž se panel vztahuje
- `dmc` – informace o datamatrixu symbolech (poloha + popisek)
- `date` – dnešní datum
- `stackup` - stackup desky
- `minDrill` - nejmenší velikost díry dle návrhových pravidel
- `minSpace` - nejmenší rozteč dvou drah dle návrhových pravidel
- `minTrace` - nejmenší šířka dráhy dle návrhových pravidel

a zároveň všechny proměnné, které podporuje KiKit
([dokumentace](https://github.com/yaqwsx/KiKit/blob/master/doc/panelizeCli.md#available-variables-in-text))

## Tvorba technologický parametrů (pravidel návrhu)

Stačí do repozitáře přidat nový JSON soubor s pravidly. Pravidla se nachází v
adresáři [designRules](../prusaman/resources/designRules/). Poté je třeba vydat
novou verzi Prusamana.
