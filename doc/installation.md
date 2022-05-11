# Instalace

Instalace a aktualizace probíhá skrze správce doplňků. Pozor, pokud je KiCAD
nainstalován skrze Flatpak, pak je třeba jeden krok navíc – viz níže.

Stáhni ZIP soubor ze [vydání projektu na
GitHubu](https://github.com/prusa3d/KiKIt_fab_prusa/releases) a nainstaluj jej
skrze správce doplňků:

![](resources/installation1.png)

Následně se Prusaman zobrazí mezi doplňky:

![](resources/installation2.png)

A v Editoru PCB přibude nová knihovna:

![](resources/installation3.png)

Při prvním spuštění Editoru PCB po installaci budeš vyzván k instalaci
backendu Prusamanu. Bez backendu Prusaman nefunguje — interně se jedná o
primárně CLI nástroj (backend), ke kterému existuje grafické rozhraní.

# Aktualizace

Pro aktualizaci stačí stáhnout novou verzi ze stránek [vydání na
GitHubu](https://github.com/prusa3d/KiKIt_fab_prusa/releases), starou verzi ve
správci doplňků odinstalovat a nainstalovat novou. Při dalším spuštění editoru
PCB budete vyzvání k aktualizaci backendu.

## Jak vyzkoušet nejnovější verzi

Prusaman má nastavené CI, které po každém commitu do repozitáře sestaví PCM
balíček. Ten je možné stáhnout a nainstalovat. Jednotlivé běhy CI jsou k
nalezení na
[https://github.com/prusa3d/KiKIt_fab_prusa/actions](https://github.com/prusa3d/KiKIt_fab_prusa/actions).
Po otevření (zpravidla posledního) běhu jsou na spodu stránky artefakty. Nás
bude zajímat artefakt s názvem "prusaman". Viz obrázek níže:

![](resources/actions.png)


# Co mám dělat, pokud mám KiCAD nainstalovaný skrze Flatpak?

Nezoufat, a před první instalací zadat několik příkazů do terminálu:

- `flatpak run --command=sh org.kicad.KiCad`, který otevře terminál uvnitř
  Flatpak KiCAD sandboxu.
- Do tohoto terminálu zadat: `python3 -m ensurepip`. Neleknout se hromady
  výpisů.
- `exit`.

Nyní stačí spustit KiCAD a pokračovat s normální instalací. V případě, že je
třeba využívat CLI rozhraní, je třeba jej spouštět z terminálu vytvořeného
pomocí `flatpak run --command=sh org.kicad.KiCad`.

Vysvětlení: Flatpatk vytváří sandbox pro každou aplikaci. Izoluje její data a
závislosti od celého systému. Flatpak KiCADu neobsahuje pip, který je nezbytný
pro instalaci všech závislostí Prusamana. Proto je třeba "vkročit do sandboxu" a
pip nainstalovat. Stejně tak CLI rozhraní je třeba pouštět zevnitř kontejneru,
jinak Prusaman nenajde KiCAD.
