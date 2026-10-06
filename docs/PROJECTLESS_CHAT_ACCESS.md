# Projektloser Chat und lokale Lesefreigaben

## Ziel

ForgeAI unterscheidet zwischen normalem Chat, lokalem Lesen und projektgebundenen
Änderungen. Ein Projekt ist keine Voraussetzung mehr für normale Unterhaltung.
Projektzwang entsteht erst dort, wo Forge Dateien erzeugen oder verändern soll.

## Projektloser Chat

Normale Chat-, Wissens-, Ideen- und Prompt-Anfragen dürfen ohne geöffnetes Projekt
an das lokale Modell gesendet werden. Ohne Projekt und ohne konkrete Lesefreigabe
wird kein lokaler Dateiinhalt in den Modellkontext aufgenommen.

## Projektpflicht für Änderungen

Erkennt das Request-Routing eine Projekt-/Dateiänderung und ist kein Projekt
geöffnet, startet Forge den Agentenworkflow nicht. Die UI meldet stattdessen:

`Kein aktuelles Projekt geöffnet. Projekt wählen oder neues Projekt erstellen.`

Der Benutzer kann ein bestehendes Projekt wählen, einen neuen Projektordner
anlegen oder abbrechen. Erst nach erfolgreicher Projektauswahl wird derselbe
Auftrag weiterverarbeitet.

Schreiboperationen bleiben weiterhin durch `WorkspaceTools` auf den geöffneten
Projektroot begrenzt. Externe oder globale Lesefreigaben erweitern diese
Schreibgrenze nicht.

## Lokales Lesen außerhalb des Projekts

Wenn ein Auftrag lokalen Inhalt lesen soll und dieser Inhalt nicht durch den
aktuellen Projektkontext gedeckt ist, benötigt Forge eine explizite
Lesefreigabe. Für konkrete Pfade wird vor dem Lesen geprüft, ob eine passende
Freigabe existiert.

Drei Freigabearten werden unterstützt:

1. **Dateifreigabe**: exakt eine ausgewählte lokale Datei.
2. **Ordnerfreigabe**: der ausgewählte Ordner und seine vorhandenen Dateien.
3. **Globaler Lesezugriff**: konkrete lokale Lesezugriffe sind ohne erneute
   Pfadfreigabe erlaubt.

Der globale Lesezugriff ist ausdrücklich kein automatischer Festplattenscan.
Forge liest nur Pfade, die für einen konkreten Auftrag benötigt bzw. ausgewählt
wurden. Er verleiht außerdem keinerlei Schreibrecht.

## Persistenz und UI

Projektinterne Datei-/Ordnerfreigaben werden in `ai_access_grants`, externe
Freigaben in `ai_external_access_grants` persistent gespeichert. Der globale
Lesemodus wird als Setting gespeichert.

Verwaltung in der UI:

`Werkzeuge -> KI-Lesefreigaben`

Dort können Datei- und Ordnerfreigaben hinzugefügt oder entfernt sowie der
globale Lesezugriff explizit ein- oder ausgeschaltet werden. Liegt der gewählte
Pfad im aktiven Projekt, verwendet der Dialog automatisch die Projektfreigabe;
außerhalb des Projekts die externe Read-Authority. Der Projektbaum und der Dialog
arbeiten damit auf derselben Projekt-Freigabequelle.

Eine Lesefreigabe verändert den Projektmodus nicht und erteilt insbesondere kein
Schreibrecht.

## Kontextgrenzen

`AIContextProvider` kann neben dem normalen Projektkontext konkrete externe
Dateien aufnehmen. Externe Ordner werden vor der Kontextbildung nur für den
aktuellen Leseauftrag expandiert. Eine persistente externe oder globale
Freigabe führt nicht dazu, dass Inhalte automatisch in jeden Chat gelangen.

Damit gilt weiterhin:

> Freigabe bedeutet Erlaubnis zum Lesen, nicht automatische Aufnahme in den Kontext.

## Sicherheitsinvarianten

- Normaler Chat benötigt kein Projekt.
- Änderungen benötigen immer ein geöffnetes Projekt.
- `WorkspaceTools` bleibt root-confined auf das aktive Projekt.
- Globaler Zugriff ist ausschließlich read-only.
- Nicht freigegebene externe Pfade werden nicht in den Modellkontext übernommen.
- Fehlende oder abgelehnte Lesefreigabe beendet den konkreten Leseversuch ohne
  erfundenen Dateiinhalt.
