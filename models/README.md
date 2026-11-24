# Öneri modelleri

Bu klasörde "Senin için" önerileri için eğitilmiş iki model var: **sanatçı benzerliği** ve **şarkı benzerliği**.
İkisi de ayrı bir projede, ListenBrainz'in açık dinleme verisiyle Kaggle'da eğitildi:
https://github.com/Xendoksia/music-recommendation-system (kod, raporlar ve bütün ölçümler orada).

**Durum (2026-11-24):** İki model de masaüstünün ve telefonun "Keşfet" bölümüne bağlandı (telefonda
`mobile/lib/data/discover.dart`) (`music/model.py`,
`music/recommend.py`). Sanatçı önerisi karma çalışıyor (`RECOMMEND_SOURCE`), şarkı önerisi yalnızca modelden geliyor.
Dosyalar `build.py` ile arka uç paketine giriyor. Şarkı modeli 2026-11-24'ten beri **2. sürüm**: knn ve RP3beta
iki ayrı komşu tablosuyla çalışıyor ve iki sıralama RRF ile birleşiyor (aşağıda). Modeller değişince
`recommend.MODEL_VERSION` ve `discover.dart` `modelVersion` bir artırılır, kayıtlı öneriler de hemen yeniden hesaplanır.

## Dosyalar

| Dosya | İçerik | Boyut |
|---|---|---:|
| `artists.json.gz` | 88.294 sanatçı: `name`, `key`, `mbid`, `listeners` | 3,5 MB |
| `artist_neighbours.i32.gz` | Her sanatçının en benzer 50 sanatçısı | 10,0 MB |
| `songs.json.gz` | 159.008 şarkı: `artist`, `title`, `key`, `mbid`, `listeners` | 8,9 MB |
| `song_neighbours.i32.gz` | Her şarkının knn ile en benzer 50 şarkısı | 17,1 MB |
| `song_neighbours_rp3.i32.gz` | Her şarkının RP3beta ile en benzer 50 şarkısı (α 0,5, β 0,6) | 19,4 MB |
| `manifest.json` | Boyutlar, ayarlar, kaynak commit ve test sonuçları | |

- JSON dosyaları bir liste. Bir kaydın listedeki sırası onun numarası.
- Komşu dosyaları gzip'lenmiş, küçük uçlu (little-endian) düz `int32` dizileri. Her kayıt için `neighbours`
  (50) sayı var. Komşular en benzerden başlayarak sıralı ve satırın kalanı `-1` ile doldurulmuş.
- Yalnızca en az 50 dinleyicisi olan sanatçılar ve şarkılar alındı. Komşu listeleri de bu kümeyle süzüldüğü için
  bazı listeler 50'den kısa. Ortalama uzunluk sanatçıda 43, şarkıda 30.
- numpy, pandas ya da parquet gerekmiyor. Python'un kendi `gzip`, `json` ve `array` modülleri yetiyor.

```python
import gzip, json
from array import array

def load(folder, kind):  # kind: "artist" ya da "song"
    with gzip.open(f"{folder}/{kind}s.json.gz", "rt", encoding="utf-8") as f:
        items = json.load(f)
    ids = array("i")
    with gzip.open(f"{folder}/{kind}_neighbours.i32.gz", "rb") as f:
        ids.frombytes(f.read())  # Windows ve Android küçük uçlu, byteswap gerekmez
    n = len(ids) // len(items)
    return items, lambda i: [j for j in ids[i * n:(i + 1) * n] if j >= 0]

artists, artist_neighbours = load("models", "artist")
by_key = {}
for i, a in enumerate(artists):  # aynı key'e düşen adlardan en çok dinleyicisi olan kalsın
    if a["key"] not in by_key or a["listeners"] > artists[by_key[a["key"]]]["listeners"]:
        by_key[a["key"]] = i
print([artists[j]["name"] for j in artist_neighbours(by_key["three days grace"])[:5]])
# ['Linkin Park', 'Breaking Benjamin', 'Papa Roach', 'Disturbed', 'Seether']
```

Bellekte sanatçı tablosu yaklaşık 18 MB, şarkıların iki tablosu yaklaşık 64 MB tutuyor. RP3beta dosyası yoksa
uygulama yalnızca knn ile çalışır. Yükleme bir kez yapılıp
saklanmalı.

## Eşleştirme

- **Sanatçı:** `key`, uygulamanın `recommend.fold()` fonksiyonuyla aynı kuralla üretildi (küçük harf, aksansız,
  Türkçe harfler sade). Uygulamadaki ad `fold()` edilip `key` ile aranır. `artwork/artist_info.json` içinde
  MusicBrainz id'si varsa `mbid` ile eşleştirmek daha güvenli. Aynı `key`'e birden çok kayıt düşerse dinleyicisi en
  çok olan seçilir.
- **Şarkı:** `key` = `fold(ilk sanatçı) + "|" + fold(sade ad)`. İlk sanatçı `listening._credit_parts` kuralıyla
  bulunur (virgül ve feat. ile bölünür, "&" bölünmez). Sade ad `artwork._plain_title` kuralıyla elde edilir
  (" - Remastered 2020" ve parantez içleri atılır). Böylece bir şarkının single ve albüm sürümleri tek şarkı sayılıyor.

## Kullanım: sanatçı önerisi

Model, `recommend.related()` fonksiyonunun Deezer'dan aldığı listenin yerini tutar: bir sanatçı için benzer
sanatçılar, en benzerden başlayarak. `score()` fonksiyonu olduğu gibi kalır, yalnızca ayarları değişir. Seçilen
(B) ayarlar şunlar:

| Ayar | Şu an (Deezer) | Model için |
|---|---:|---:|
| `SEEDS` | 10 | 30 |
| `RELATED` | 20 | 50 |
| `SEED_DECAY` | 0,5 | 0,75 |

- Model bir sanatçıyı tanımıyorsa o sanatçı için Deezer'a düşülür (karma çözüm). Kullanıcının kararı bu yönde.
- Fotoğraflar ve en popüler şarkılar (`top_tracks`) Deezer'dan gelmeye devam eder.
- Model internetsiz çalışır. Deezer yalnızca yedek ve görseller için gerekir.

## Kullanım: şarkı önerisi

Aynı puanlama şarkılara uygulanır: kullanıcının en çok dinlediği 30 şarkı başlangıç olur, her birinin 50 benzeri
okunur ve `score()` ile sıralanır (`SEED_DECAY` 0,75).

- **Keşif** ("Senin için"): Kullanıcının dinlediği sanatçıların şarkıları elenir. Geriye yeni sanatçıların
  şarkıları kalır.
- **2. sürüm, RRF:** Aynı tohumlarla `score()` iki kez çalışır, biri knn, diğeri RP3beta komşularıyla. İki sıralı
  listenin ilk 50 şarkısı birleşir: şarkının puanı her listede `1 / (60 + sıra + 1)` değerlerinin toplamı (sıra 0'dan
  başlar), eşitlikte dinleyicisi çok olan önce gelir (`recommend.fuse`, telefonda `fuse`). Yeni/bilinen ayrımı ve
  sanatçı başına 2 sınırı bu birleşik listeye uygulanır. İlk 50'ler tükenirse (dinlenen sanatçılar ayrılınca liste
  10'a yetmeyebiliyor) iki listenin geri kalanı aynı kuralla tamamının üzerinden birleşip arkaya eklenir.
- **Buna benzeyenler** (`alike_songs`) yalnızca knn tablosunu kullanır. Telefonun model işçisi RP3beta'yı yüklemez.
- **Bütün şarkılar:** Yalnızca dinlenmiş şarkılar elenir. Bu modda öneriler çoğunlukla bilinen sanatçıların başka
  şarkıları olur ("Sevdiğin sanatçılardan" gibi bir bölüm için uygun).

## Ölçümler

Modeller, ListenBrainz kullanıcılarının bir kısmı ayrılıp dinlediklerinin %20'si gizlenerek ölçüldü. Her yöntem
uygulamanın `score()` kuralıyla çalıştırıldı.

**Sanatçı modeli** (8.518 test kullanıcısı, 12 öneri)

| Yöntem | recall@12 | hit@12 | NDCG@12 |
|---|---:|---:|---:|
| Popülerlik | 0,016 | 0,519 | 0,111 |
| İlk knn (cosine, 10/20/0,5) | 0,069 | 0,791 | 0,316 |
| **Seçilen ayarlar** | **0,076** | **0,812** | **0,381** |

Kullanıcının kendi verisinde (102 sanatçı tek tek gizlendi) model, Deezer'ın benzer sanatçı listesinden iyi çıktı:
ilk 12'de yalnız modelin bulduğu 15, yalnız Deezer'ın bulduğu 3 sanatçı oldu (p = 0,008). Kör karşılaştırmada
kullanıcı modelin listesini seçti.

**Şarkı modeli, 2. sürüm** (5.000 genel test kullanıcısı, 12 öneri, ayrıntı `manifest.json` ve model projesinde
`reports/sarki_iyilestirme.md`): knn + RP3beta RRF, 1. sürümün knn'ine göre keşifte recall@12 %17, NDCG@12 %14,
bütün şarkılarda recall@12 %7 daha yüksek (bütün şarkılarda recall@12 0,0811, hit@12 %85,6, NDCG@12 0,404).

**Şarkı modeli, 1. sürüm** (5.000 test kullanıcısı, 12 öneri)

| Görev | Şarkı modeli | Uygulamanın şu anki yolu | En iyi diğer rakip |
|---|---:|---:|---:|
| Keşif, recall@12 | **0,036** | 0,011 (sanatçı başına 3 şarkı) | 0,013 (sanatçı başına 1 şarkı) |
| Keşif, hit@12 | **%35** | %14 | %19 |
| Bütün şarkılar, recall@12 | **0,087** | 0,004 | 0,050 (kendi sanatçılarının en popüler şarkıları) |

"Uygulamanın şu anki yolu", sanatçı modelinin önerdiği yeni sanatçıların en popüler şarkılarını göstermek demek.
Şarkı modeli yeni sanatçılardan doğrudan şarkı seçtiğinde bu yoldan yaklaşık 3 kat isabetli.

## Sınırlar

- **Veri tazeliği:** Sanatçı modeli ListenBrainz'in tüm zaman istatistiklerinden, şarkı modeli bunlarla birlikte
  son 15 günün dinlemelerinden eğitildi (Kasım 2026). Yeni çıkan sanatçı ve şarkılar için modeller ayda bir
  yenilenmeli.
- **Kapsam:** Az dinlenen sanatçılar ve şarkılar (50'den az dinleyici) yok. Türkçe pop kapsamı zayıf. Bunlar için
  Deezer yedeği gerekli.
- **Popülerlik:** Seçilen sanatçı ayarları önerileri biraz daha bilinen sanatçılara kaydırıyor. Bu, genel testte
  en iyi sonucu verdiği için seçildi.

## Yenileme

Model projesinde:

```
python -m src.export_app "<bu repo>/models" --two
```

Komut bu klasördeki dosyaları ve `manifest.json`'u yeniden yazar. Telefon uygulaması beş `.gz` dosyasının bir kopyasını
`mobile/assets/models/` içinde taşır (Android derlemesi uygulama klasörü dışındaki dosyaları almıyor). Yenilemeden
sonra onları da kopyala, `mobile/test/discover_test.dart` iki kopya farklıysa hata verir. Önce ilgili Kaggle çıktılarının
(`kaggle/tune/output`, `kaggle/song_train/output`) indirilmiş olması gerekir.
