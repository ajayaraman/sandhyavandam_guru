# Phase 0.5 — Sanskrit STT shootout results

Run on 10 mantra IDs (each: clean + with_error).

- Whisper model: `large-v3`
- Gemma model (LM Studio): `gemma-4-e4b-it`

## Whisper
- median CER (clean): **0.164**
- median latency (s): **8.48**
- religious-error recall: **1.00** (10/10)

## Gemma 4 E4B (LM Studio)
- median CER (clean): **nan**
- median latency (s): **nan**
- religious-error recall: **0.00** (0/0)

## Per-clip details

| mantra | len | dur | W-CER | W-lat | W-err? | G-CER | G-lat | G-err? |
|---|---|---|---|---|---|---|---|---|
| m10_asavaadityo | short | 8.48s | 0.946 | 7.2s | **yes** | nan | nans | — |
| m06_achyuta_short | short | 10.2s | 0.164 | 6.5s | **yes** | nan | nans | — |
| m15_nyaasam | short | 11.06s | 0.541 | 67.7s | **yes** | nan | nans | — |
| m08_gayatri_arghya | medium | 12.24s | 0.023 | 7.5s | **yes** | nan | nans | — |
| m03_sankalpam | medium | 11.74s | 0.040 | 6.8s | **yes** | nan | nans | — |
| m22_harihara | medium | 18.92s | 0.088 | 8.9s | **yes** | nan | nans | — |
| m24_samarpanam | medium | 20.88s | 0.114 | 8.5s | **yes** | nan | nans | — |
| m26_rakshaa | medium | 23.3s | 0.072 | 8.5s | **yes** | nan | nans | — |
| m05_praashanam_pratah | long | 34.42s | 0.702 | 94.8s | **yes** | nan | nans | — |
| m18_mitrasya_pratah | long | 60.68s | 0.958 | 41.9s | **yes** | nan | nans | — |

## Transcripts

### m10_asavaadityo
- **expected:** `asavaadityo brahma brahmai vaham asmi`
- whisper (clean): `असावादित्यो ब्रह्मा प्रम्है वाहमस्मी`
- whisper (with_error): `asavadityo brahma brahmai vaham asmi`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m06_achyuta_short
- **expected:** `om achyutaaya namaha om anantaaya namaha om govindaaya namaha`
- whisper (clean): `oom atya daa yanamaha oom anantaaya namaha oom govindaaya namaha`
- whisper (with_error): `omkabindaia namaha`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m15_nyaasam
- **expected:** `saavitrya rushih vishvaamitraha nichrudgaayatree cchandaha savitaa devataa`
- whisper (clean): `saivitrya rushih vishvaamitraha lasting`
- whisper (with_error): `savitrya rushih vishvaamitraha touch chestnetes`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m08_gayatri_arghya
- **expected:** `om bhoorbhuvassuvah tatsaviturvarenyam bhargo devasya dheemahi dheeyo yonah prachodayaat`
- whisper (clean): `o bhoorbhuvassuvah tatsaviturvarenyam bharko devasya dheemahi dheeyo yonah prachodayaat`
- whisper (with_error): `aum bhoorbhuvassuvah tatsaviturvarenyam bhargo devasya dheemahi dheeyo yonah prachodayaat`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m03_sankalpam
- **expected:** `mama upaatta samasta durita kshaya dwaaraa shree parameshwara preetyartham praatah sandhyaam karishye`
- whisper (clean): `mama upaatta samasta durita kshaya dwaaraa shree parameshwara preetyartham fran a sandhyaam karishye`
- whisper (with_error): `mamaa opaatta samasta durita kshaya dwaaraa shree parameshwara preetyartham proportah sandhyaam karishye`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m22_harihara
- **expected:** `rutagam satyam para brahma purusham krushna pingalam oordhvaretam viroopaaksham vishva roopaaya vai namaha vishwa roopaaya vai namaha om namaha iti`
- whisper (clean): `prithagam satyam para brahma purusham krushna pingalam eyebroordhvaretam viroopaaksham vishva roopaaya vai namaha eyebrvishwa roopaaya vai namaha om namaha iti`
- whisper (with_error): `vishva roopaaya vai namaha om namaha iti`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m24_samarpanam
- **expected:** `kaayena vaachaa manasendriyairvaa buddhyaatmanaavaa prakrute svabhaavaat karomi yadyat sakalam parasmai naaraayanaayeti samarpayaami`
- whisper (clean): `kayaena vaachaa manasendriyairvaa buddhyaatmanaavaa prakrute svabhaavaatkarangaromi yadyat sakalam parasmai neighbnaaraaya aayeti samarpayaami`
- whisper (with_error): `kahena vaachaa manasendriyairvaa buddhaatmanaavaa prakrute svabhaavaat kahkahaaromi yadyat sakalam parasmai kahkahaaromi yadyat sakalam parasmaibreviya`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m26_rakshaa
- **expected:** `adya no devaa savitaa prajaavat saavee soubhagam para duswapneeya suva vishwaani deva savitaa duritaani paraa suvaa yad bhadram tama asuva`
- whisper (clean): `adhya no devaa savitaa prajaavat savee soubhagam para duswapneeya suvabishwaani deva savitaa duritaani paraa suva minneyad bhadram tama asuva`
- whisper (with_error): `adhyaa no deva saavitaa prajaavat saavee soubhagamihoodiam para duswapneeya suva vani deva savitaa duritaani para suva aadhyaa no deva saavitaa prajaavat saavee seviyyad bhadram tama asuvaa severe yad bhadram tama asuvaa`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m05_praashanam_pratah
- **expected:** `sooryashcha ma manyushcha manyu patayashcha manyukrutebhya paapebhyo rakshantam yad raatryaa paapa maa karsham manasaa vaachaa hastabhyam padbhyaam udarena shishna raatreeh tadaa valumbatu yad kincha duritam mayi idam aham mama amruta yonou soorya jyotishee juhomi svaahaa`
- whisper (clean): `sooryahshcha ma manyushcha manyu patehashchaya manifested versi n hteen oturability of the lord is manifested in religion oure kerimah prakashantham yad raatryaa paapa maa karshamthelessomedbenben it is a small lesson gr pointers to each सूर्य ज्योतिषी ज्योमिस्वाह`
- whisper (with_error): `so yashcha ma manyushcha manyu patayashcha manyukrutebhya paapebhyo rakshantam eyebryan raatryaa paapa maa karsham psakiyan raatryaa paapa maa karsham manusa vaachaa hastabhyam padbhyaam udare na shishnaya ratreeh tadaa valumbatu eyebryan raatryaa tadaa valumbatu yath kincha duritam mayi yidam aham mama amruta yonou saryaa jyotishee juhomi svaahaa`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

### m18_mitrasya_pratah
- **expected:** `mitrasya charshani druto aavo devasya sanaasi dyumnam chitra shravasthamam mitro janaan yataayati bruvaano mitro dataara pruthveem udatyam mitra srushtir nimishaa abhishte mitraaya havyam grutavajjuhotaa prashamitra marto astu prayaswaan yasta aaditya shikshati vrutena na hanyate na jeeyate dvoto sannama aho asnodhyamtito na doorata`
- whisper (clean): `प्रतवज्जुद्भोता प्रशमित्रमर्तो अस्तु प्रयस्वान् यस्तादित्य शिक्षाति वृतेन नहनयते नजीयते त्वोतो सन्नाम अहो अस्नो ध्यामित्तितो नादूरात`
- whisper (with_error): `s s s s s s s s s s s s s s s s s s s s ch ch ch ch ch ch`
- ⚠ gemma error: `Error code: 400 - {'error': "Invalid 'content': 'content' objects must have a 'type' field that is either 'text' or 'image_url'."}`

## Recommendation

**Pick: Whisper.**

Decision rule: religious-error recall (primary), then CER (tiebreak), then latency.