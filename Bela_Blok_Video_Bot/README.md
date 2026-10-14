# Bela Blok – besplatni bot za kratke videe

**Status:** Generator je izrađen i probno renderiran. Instagram i TikTok **nisu povezani niti je ijedna objava poslana**. Objavljivanje se aktivira nakon što vlasnik postavi svoje API ključeve i Cloudflare Pages projekt.

## Kako funkcionira

- GitHub Actions svakog jutra izrađuje pet MP4 videa (720 × 1280, 24 fps, ~11 sekundi) koristeći isključivo slike Bela Blok aplikacije.
- Videi su animirani marketinški slajdovi s originalnom sintetičkom glazbom i hrvatskim tekstom. Ne koriste plaćeni AI niti generiraju nove videosnimke igre.
- Cloudflare Pages Free služi videe putem HTTPS-a. Potreban je **javno dostupan izravan MP4 URL** jer ga Buffer API ne može preuzeti iz privatne pohrane.
- Buffer Free preko službenog GraphQL API-ja zakazuje pet Instagram Reels i pet TikTok videa dnevno, u 09:15, 11:45, 14:15, 17:30 i 20:15 (Europe/Zagreb).
- Profilima mora biti omogućeno automatsko objavljivanje; Buffer ili društvena mreža mogu odbiti pojedini video. Provjeravaj rezultate u Bufferu.

## Aktivacija (jednokratno)

1. Na GitHubu napravi **novi public repozitorij** naziva `bela-blok-video-bot`, grana `main`. U njega kopiraj sav sadržaj ove mape, uključujući skrivenu `.github/workflows/daily.yml` mapu. Ako ćeš koristiti GitHubovo web sučelje, učitaj raspakirane datoteke, a ne ZIP kao jednu datoteku. Repo je public zato što su GitHub Actions minute za privatni repozitorij ograničene, dok je izvorni kod i screenshotove aplikacije moguće javno dijeliti.
2. Otvori besplatan [Cloudflare Pages](https://dash.cloudflare.com/) projekt s nazivom npr. `bela-blok-media`. U Cloudflareu: Workers & Pages → Create application → Pages → Direct Upload (ili ekvivalentna opcija); napravi projekt. U Cloudflare profilu pronađi **Account ID** i izradi **API Token** kojem je dozvoljeno uređivanje Cloudflare Pages projekata. Token mora biti tajna.
3. U GitHub repo → Settings → Secrets and variables → Actions → **Secrets** dodaj:
   - `BUFFER_API_KEY` – Buffer → Settings → API → Create API key.
   - `CLOUDFLARE_API_TOKEN` – Cloudflare API token za Pages.
   - `CLOUDFLARE_ACCOUNT_ID` – tvoj Cloudflare account ID.
   **NIKADA ne stavljaj ključeve u kod, screenshot, issue ili README.**
4. U istom ekranu pod **Variables** dodaj:
   - `CLOUDFLARE_PROJECT_NAME` = `bela-blok-media` (ili stvarni naziv projekta)
   - `VIDEO_PUBLIC_BASE` = `https://bela-blok-media.pages.dev` (ili stvarni link koji ti Cloudflare dodijeli)
   - Ako u Bufferu imaš više Instagram/TikTok profila, opcionalno `BUFFER_INSTAGRAM_CHANNEL_ID` i `BUFFER_TIKTOK_CHANNEL_ID`.
5. U Bufferu spoji Instagram i TikTok. Instagram mora biti profesionalni račun. Provjeri da oba imaju uključen **automatic publishing** gdje je dostupan i da nije pauzirana Queue.
6. GitHub → Actions → **Bela Blok – 5 videa dnevno** → Run workflow → `preview` za testni ZIP s pet videa u Artifacts. Kad želiš da stvarno zakazuje, Run workflow → `publish`. Od idućeg jutra svakodnevno radi samo.

## Lokalno testiranje

Na Linuxu ili Windowsu s Python 3.12, FFmpeg:

```bash
pip install -r requirements.txt
python generate.py --count 5 --preview
```

Test Buffer veze (bez objave):

```bash
# Postavi BUFFER_API_KEY kao varijablu okoline lokalno (ne u GitHub kod)
python publish_buffer.py --test-connection
```

## Važne granice besplatne verzije

- Buffer Free ima **10 zakazanih objava po kanalu odjednom**. Bot svakog dana kreira do pet, ali ako je red prethodno napunjen, API može vratiti grešku. Nema jamstva da svih 10 objava svakog dana zaista uspije.
- GitHub Actions i Cloudflare Pages imaju besplatne kvote i pravila korištenja; 0 € vrijedi samo unutar njih. GitHub Actions u public repozitoriju može biti onemogućen nakon dulje neaktivnosti.
- Cloudflare Pages pojedinačna datoteka ima ograničenje veličine (ovdje je ugrađena provjera <24 MiB).
- Čisti MP4-e starije od sedam dana, a `state.json` čuva ID-je zakazanih objava. Upozorenje: `state.json` je verzioniran kao jednostavna zaštita od dupliciranog objavljivanja; ako GitHub Actions padne usred slanja, provjeri Buffer Queue prije ponavljanja.
- Ključne riječi i opisi su unaprijed definirani predlošci u `generate.py`, a ne neograničeno AI generiranje novih ideja. Rotacijom se dobivaju varijacije, ali nakon nekog vremena može doći do ponavljanja tema.
- Za komercijalno objavljivanje moraš poštovati pravila TikToka i Mete te prava na audio/vizuale. Ugrađeni zvuk je izvorno sintetiziran, bez tuđe glazbe.
- Nemoj koristiti GitHub Pages za ovaj medijski hosting. GitHub Pages nije zamišljen kao besplatni hosting promocije komercijalnih aplikacija. U ovoj varijanti GitHub služi samo za automatizaciju i pohranu izvornog koda, a videe javno poslužuje Cloudflare Pages.

## Službena dokumentacija

- [Buffer API: video post](https://developers.buffer.com/examples/create-video-post.html)
- [Buffer API: hosting](https://developers.buffer.com/guides/hosting-media.html)
- [Buffer API: API key](https://developers.buffer.com/guides/authentication.html)
- [Buffer Free](https://buffer.com/pricing)
- [Cloudflare Pages Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)
