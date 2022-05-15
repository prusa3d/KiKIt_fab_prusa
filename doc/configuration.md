# Nastavení projektu

Celý projekt je řízen souborem `prusaman.yaml`. Ten obsahuje veškerá nastavení
výrobního procesu. Zároveň se očekává, že v projektu budou existovat soubory
`readme.freza.template.txt` a `readme.panel.template.txt`, které obsahují vzory
readme souborů pro výrobní podklady. V těch je možno používat proměnné (viz
níže).

`prusaman.yaml` je [YAML soubor](https://www.cloudbees.com/blog/yaml-tutorial-everything-you-need-get-started), který má následující strukturu:

```.yaml
revision: 10 # Specifikace revize desky
board_id: 1038 # Přidělené ID desky (shodné s datamatrixem)
bom_filer: pnb # nebo legacy - viz Filtrování BOMu níže
panel:
    type: kikit # nebo manual nebo script. Určuje, jak je tvořen panel
    configuration: kikit.json # Cesta ke konfiguračnímu souboru KiKitu, který je možné vytvořit i z GUI
```

Ukázkové projekty jsou k nalezení v adresáři [examples](examples).

## Filtrování BOMu

Prusaman podporuje dva typy filtrování BOMu:
- `legacy` – je původní styl (viz
  [Confluence](https://cfl.prusa3d.com/pages/viewpage.action?pageId=41468219)),
  který se řídí hvězdičkou v políčku ID.
- `pnb` – je nový styl. Pokud má symbol pole `PnB`, tak:
    - `#` – neosazuji, nakupuji
    - `dnf` – *ne*osazuji, *ne*nakupuji
    - `` (prázdné pole) – osazuji, nakupuji

Doporučujeme používat styl `pnb` jelikož je inutitivnější. Zároveň se u všech
stylů ignorují symboly, jejižch reference začíná na jedno z: `#` (symboly
napájení), `M`, `NT`, `G`.

## Specifikace panelu

Panel je možné specifikovat pomocí jednoho ze třech nástrojů:
- `kikit` – Použije se [KiKit](https://github.com/yaqwsx/KiKit) pro generování
  panelu. V poli `configuration` je možné uvést cestu k souboru s parametry,
  který se píše buď ručně nebo tvoří pomocí GUI.
- `script` – Použije se uživatelem dodaný skript pro výrobu panelu. Jména/cesta
  ke skriptu je předána v poli `script`. Očekává se, že skript dostane dva
  argumenty: `skript <cesta_ke_zdrojové_desce> <cesta_k_výstupu>`. Tato možnost
  je vhodná, pokud si např. uživatel napsal vlastní panelizační skript pomocí
  KiKitu (protože panel není možné naspecifikovat jen z CLI)
- `manual` – Panel je manuálně nakreslen. V tento moment se v poli `source`
  specifikuje cesta k panelu.

## Jak specifikovat panely dle Prusa Guide v KiKitu:

- jako frame použít `plugin`, `code` je `prusaman.Frame` a jako argument dostane
  požadovanou utilizovanou výšku panelu (jedno z 143mm, 154mm, 196mm)
- pro tvorbu tooling holes použít `plugin`, `code` je `prusaman.Tooling`.
  Tooling plugin nemá žádné argumenty.
- nezapomeň uvést v sekci `post`: `origin: bl` a v sekci `page`: `anchor: bl` a
  `posx: 0mm` a `posy: 0mm`.

K dispozici je [příklad](examples/simple_pnb/kikit.json).

# Šablony a argumenty

V momentě, kdy specifikujete výrobní proces, existují nějaké neznámé (např.
rozměry panelu, datum generování apod.) Pro tyto účely je možné používat
proměnné v šablonách readme a v konfiguračním YAML souboru. Proměnné se
specifikují jako v Pythonu – tj. do složených závorek, např: `Dnes je {date}`.

Podporovány jsou následující proměnné:
- `size` – velikost desky k níž se panel vztahuje
- `dmc` – informace o datamatrixu symbolech (poloha + popisek)
- `date` – dnešní datum

a zároveň všechny proměnné, které podporuje KiKit
([dokumentace](https://github.com/yaqwsx/KiKit/blob/master/doc/panelizeCli.md#available-variables-in-text))
