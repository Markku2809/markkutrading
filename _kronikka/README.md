# US500 Kronikka verkossa

Julkinen katsaus osoitteessa https://aimtrading.fi/kronikka/. Etusivujen painikkeet avaavat suomenkielisen katsauksen.

GitHub Actions hakee julkiset hintalähteet, uutisotsikot, analyytikkojen maininnat ja tapahtumakalenterin kymmenen minuutin ajastuksella. GitHubin ajastus ja sivujulkaisu voivat viivästyä. Sivulla näkyy katsauksen aika ja ikä sekä lähdekohtaiset ajat. Tämä ei ole reaaliaikainen markkinadatapalvelu.

30.9.2026 lisättiin cron-job.org-palveluun erillinen verkkoajastus, joka käynnistää saman työnkulun 10 minuutin välein. GitHubin oma ajastus säilyy varalla. Verkkoajastus ei tarvitse kotikoneen tai selaimen käynnissäoloa; GitHubin suoritusjono ja lähteiden viiveet voivat edelleen vaikuttaa julkaisuaikaan.

Ajastin käyttää HTTPS POST -pyyntöä `https://api.github.com/repos/Markku2809/markkutrading/actions/workflows/kronikka-pages.yml/dispatches` ja runkoa `{"ref":"main"}`. GitHubin käyttöavain on tallennettu vain ajastuspalvelun Authorization-otsakkeeseen. Avaimen kohde on vain `Markku2809/markkutrading`, oikeudet Actions (read/write) ja pakollinen Metadata (read-only), voimassaolo 29.12.2026 asti. Avain uusitaan GitHubissa ja korvataan ajastuspalvelussa ennen sen vanhenemista; sitä ei tallenneta lähdekoodiin, lokiin eikä julkiselle sivulle.

Selaimen päivityspainike hakee viimeksi julkaistun katsauksen. Se ei käynnistä uutta tiedonhakua GitHubissa. Automaattinen tarkistus hakee katsauksen kerran minuutissa. Aikaleimat tarkistetaan 15 sekunnin välein myös silloin, kun automaattinen haku on pois käytöstä. Yli 15 minuuttia vanha katsaus tai yli 20 minuuttia vanha hintatieto keskeyttää suunta-arvion. Lähdevirhe näkyy aina; puuttuvaa hintaa ei korvata arvatulla suunnalla.

Verkkohaku katkaistaan 15 sekunnin kuluttua, jotta päivityspainike vapautuu myös yhteyden jäädessä odottamaan. Vanhenemisrajat säilyvät voimassa myös ajastimen häiriössä.

Tiedonkeruu käyttää vain julkisia lähteitä. Paikallisen IG-scannerin dataa, lokitiedostoja, tunnuksia tai historiaa ei siirretä. Verkkoversion historia alkaa sen ensimmäisestä julkaisusta. Aiemman verkkokatsauksen päivän raportit ja viimeiset 15 muutosta säilytetään seuraavassa julkaisussa, kun edellinen katsaus on saatavilla.

`publish.py` tuottaa `kronikka/data/state.json`-tiedoston. `stage.py` kokoaa koko olemassa olevan sivuston julkaisuun ja jättää sisäisen `_kronikka`-hakemiston ja Git-tiedostot pois. Julkaisu ei muuta kotikoneen sovellusta.

Pagesin lähteeksi asetetaan GitHub Actions. Työnkulku julkaisee koko sivuston päähaaran muutoksissa, käsin käynnistettäessä ja ajastetusti. Muut työnkulut voivat edelleen päivittää sivuston tiedostoja; seuraava Kronikan ajastettu julkaisu sisältää ne.
