1 CW lijkt 5 a 10x te veel
'jogging' lijkt niet helemaal te kloppen



logbook 27-01-2026 21:20 Whatsapp met Jan Smit:
gestart
1 CW : lijkt ok
1 CW : er gebeurt niks. De positie werd ook niet geupdate op het scherm. (is het report formaat correct??)


logfile staat op diyaudio 


Jan stuurt ook de output van de sounddevices op, zodat ik kan kijken welke hij moet kiezen (babyface pro (analoog 1 en 2; 3 en 4 uit))
- code aangepast zodat aparte input en output device kan worden gekozen

Opmerkingen Jan:


- Op Nice GUI zou Up en Down in volgorde omgekeerd moeten zijn, om in lijn te zijn met de IN OUT volgorde.

- Bij succesvolle homing verwacht ik de weergave van 0,0,0 op de niceGui. De log laat die ook zien.
MPOT: Er zou geen 0,0,0 te zien moeten zijn. Ik betwijfel echter wel of wat je nu ziet correct is

- Niet uit Alarm te krijgen. Ook niet met 'REHOME'

- 'Jog' knoppen verbeteren en ook grotere afstanden. bijv. 1, 10, 60, 120 graden/mm

- Machine position NOK after homing, maar ook niet bij startup, waardoor de eerste beweging raar kan zijn.

- Altijd eerst de controller resetten voordat we met python connecten. (N.B.: Dat gebeurde in GRBL/Arduino automatisch). Feit is dat in grblHAL dit niet gebeurt. zie ook: https://github.com/grblHAL/core/wiki/For-sender-developers#connecting
MPOT: Ik heb het gelezen en ik denk dat er staat dat iemand anders de connection moet sluiten. Ik ben er nog niet van overtuigd dat het een NFS probleem is
en het lijk te moeilijk om snel tegen gekkigheid van een andere sender te kunnen.