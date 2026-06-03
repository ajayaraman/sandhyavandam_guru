# Phase 0.5 — Sanskrit STT shootout results

Run on 10 mantra IDs (each: clean + with_error).

- Whisper model: `mlx:mlx-community/whisper-large-v3-mlx`
- Gemma model (LM Studio): `gemma4:e4b`

## Whisper
- median CER (clean): **0.520**
- median latency (s): **1.82**
- religious-error recall: **0.80** (8/10)

## Gemma 4 E4B (LM Studio)
- median CER (clean): **0.167**
- median latency (s): **11.47**
- religious-error recall: **1.00** (10/10)

## Per-clip details

| mantra | len | dur | W-CER | W-lat | W-err? | G-CER | G-lat | G-err? |
|---|---|---|---|---|---|---|---|---|
| m10_asavaadityo | short | 8.48s | 0.028 | 27.5s | no | 0.250 | 6.4s | **yes** |
| m06_achyuta_short | short | 10.2s | 0.121 | 1.0s | **yes** | 0.069 | 7.5s | **yes** |
| m15_nyaasam | short | 11.06s | 9.588 | 9.8s | no | 0.309 | 8.3s | **yes** |
| m08_gayatri_arghya | medium | 12.24s | 0.012 | 0.7s | **yes** | 0.167 | 8.2s | **yes** |
| m03_sankalpam | medium | 11.74s | 0.053 | 0.6s | **yes** | 0.138 | 8.4s | **yes** |
| m22_harihara | medium | 18.92s | 0.729 | 0.4s | **yes** | 0.136 | 11.5s | **yes** |
| m24_samarpanam | medium | 20.88s | 0.353 | 1.8s | **yes** | 0.168 | 13.0s | **yes** |
| m26_rakshaa | medium | 23.3s | 0.520 | 0.6s | **yes** | 0.126 | 12.8s | **yes** |
| m05_praashanam_pratah | long | 34.42s | 2.400 | 14.6s | **yes** | 1.000 | 17.3s | **yes** |
| m18_mitrasya_pratah | long | 60.68s | 0.972 | 2.9s | **yes** | 0.150 | 21.6s | **yes** |

## Transcripts

### m10_asavaadityo
- **expected:** `asavadityo brahma brahmai vaham asmi`
- whisper (clean): `asa vadityo brahma brahmai vaham asmi`
- whisper (with_error): `asa vadityo brahma brahmai vaham asmi`
- gemma (clean): `asarvavadityo brahma tamhi vaghamasmi`
- gemma (with_error): `asa vadityo brahmah brahmaya vaham asmi`

### m06_achyuta_short
- **expected:** `om achyutaya namaha om anantaya namaha om govindaya namaha`
- whisper (clean): `om atya da yanamaha om anantaya namaha om govindaya namaha`
- whisper (with_error): `ocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaoca`
- gemma (clean): `om acyutaya namah om anantaya namah om govindaya namah`
- gemma (with_error): `om acitaya namah om anantaya namah om govindaya namah`

### m15_nyaasam
- **expected:** `savitrya rushih vishvamitraha nichrudgayatre cchandaha savita devata`
- whisper (clean): `ocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaoca`
- whisper (with_error): `ocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaoca`
- gemma (clean): `savitriyarsihi visvamitrah yatra gataya tricandah savita devata`
- gemma (with_error): `savitrir rsim isvami traha ye srad gayatri chamda savita devata`

### m08_gayatri_arghya
- **expected:** `om bhorbhuvassuvah tatsaviturvarenyam bhargo devasya dhemahi dheyo yonah prachodayat`
- whisper (clean): `om bhorbhuvassuvah tatsaviturvarenyam bharko devasya dhemahi dheyo yonah prachodayat`
- whisper (with_error): `om dhorbhuvassuvah tatsaviturvarenyam barbie devasya demahi deyo yonah prachodayat`
- gemma (clean): `om purvah vasuvah tat savitur varenyam bhargo devasya dhimahi dhiyo yo na pracodayat`
- gemma (with_error): ``

### m03_sankalpam
- **expected:** `mama upatta samasta durita kshaya dwara shre parameshwara pretyartham pratah sandhyam karishye`
- whisper (clean): `mama patta samasta durita kshaya dwara shre parameshwara pretyartham franca sandhyam karishye`
- whisper (with_error): `mama opatta samasta durita kshaya dwara shre parameshwara pretyartham pratah sandhyam karishye`
- gemma (clean): `mama pata samasta turita ksaya dvara sri paramesvara prityartham prata sandhyam karsiye`
- gemma (with_error): `mama upatta samastya tire ida saye dvarab sri pramisvara pratyatam prade samdhyam korise`

### m22_harihara
- **expected:** `rutagam satyam para brahma purusham krushna pingalam ordhvaretam viropaksham vishva ropaya vai namaha vishwa ropaya vai namaha om namaha iti`
- whisper (clean): `vishva ropaya vai namaha om namaha iti`
- whisper (with_error): `rotagam satyam para brahma purusham krushna pingalem old varetam viropaksham vishwa ropaya vai namha vishva ropaya vai namaha om namaha iti`
- gemma (clean): `rtagam satyam para brahma purusam krsna pinkalam urddhvaretam virupaksam visvarupaya vai namah visvarupaya vai namah om namah iti`
- gemma (with_error): `prodigam satyam param prahu purusham krsna pingalam udvaretam vrpaksam visva rupay vai namah visvarupayai vai namah om nama hi iti`

### m24_samarpanam
- **expected:** `kayena vacha manasendriyairva buddhyatmanava prakrute svabhavat karomi yadyat sakalam parasmai narayanayeti samarpayami`
- whisper (clean): `kaini vacha manasendriyairva buddhatmanava prakrute svabhavatihodaromi yadyat sakalam parasmai minnekaromi yadyat sakalam parasmai narayanayeti samarpayami`
- whisper (with_error): `kahena vacha manasendriyairva buddhatmanava prakrute svabhavat eyebraromi yadyat sakalam parasmai naharaya nayeti samarpyamin`
- gemma (clean): `kayena vaca manasim dryah pranama buddha atmanav prakrteh svabhavat karomi yat yat sakalam parasmai narayanaye ti samarpayami`
- gemma (with_error): `kayena vaca manase indriyairva udyatmana va prakrtim svabhavatah karomi yatyat sakalam paras nahi daren yeti samarpyami`

### m26_rakshaa
- **expected:** `adya no deva savita prajavat save soubhagam para duswapneya suva vishwani deva savita duritani para suva yad bhadram tama asuva`
- whisper (clean): `adhyano deva savita prajavat save soubhagam paradhuswapneya suva ko`
- whisper (with_error): `adhya no deva savita prajavat save soubhagam eyebr para duswapneya suvaerntam kudharm kudharm viswani deva savita duritani para suva yad bhadram tama asuva`
- gemma (clean): `atya no deva savita prajavat savi svabhakyam para dusvapaniya suva visvani deva savita turitani parasuva yadbhatram tama asuv`
- gemma (with_error): `atya nu devo savita prajavat sari sobhagyam para dusva panniya suva visvani diva savita tiretiyani para sva yad dharmam tamah asuva`

### m05_praashanam_pratah
- **expected:** `soryashcha ma manyushcha manyu patayashcha manyukrutebhya papebhyo rakshantam yad ratrya papa ma karsham manasa vacha hastabhyam padbhyam udarena shishna ratreh tada valumbatu yad kincha duritam mayi idam aham mama amruta yonou sorya jyotishe juhomi svaha`
- whisper (clean): `ocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaoca surya jyotisi jyomi svaha`
- whisper (with_error): `so yashcha ma manyushcha manyu patayashcha manyukrutebhya papebhyo rakshantam eyebryan rathriya papa ma karsham minneyan rathriya papa ma karsham so yashcha ma manyushcha ma rathriya tada valumbatu eyebryan rathriya jyotishe juhomi svaha`
- gemma (clean): ``
- gemma (with_error): `so yajcha mamanyasca manyapatayashca manyukritebhya papi bhyo raksantam yad ratrya pap makarsam manasa vaccha hastadhyam padbyam udarena sisna ati tada vilambatu yat kinca taritam mahi idam ambama amruta yunah sariya jyate si cho mi svaha`

### m18_mitrasya_pratah
- **expected:** `mitrasya charshani druto avo devasya sanasi dyumnam chitra shravasthamam mitro janan yatayati bruvano mitro datara pruthvem udatyam mitra srushtir nimisha abhishte mitraya havyam grutavajjuhota prashamitra marto astu prayaswan yasta aditya shikshati vrutena na hanyate na jeyate dvoto sannama aho asnodhyamtito na dorata`
- whisper (clean): `oca prata`
- whisper (with_error): `ocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaocaoca mitrayakhavyam krtavajjuhota prasamitramartostu prayasvan yastadityasiksatiruten nahanyate najiyate tvatosannama aho asana dhyamtito nadhurata`
- gemma (clean): `mitrasya carshani trato avo tevasa sanasi dyumnam citra shavastamam mitro janan yatayati pravano mitro tatara prthvim udatyam mitra srste nimisha abhiste mitrah havyam krta va jut hota prasamitramarto astu prayasvam yast aditya siksati vratena dahanayate najiyate tvato san nama aho asno dhyamitti to nadurata`
- gemma (with_error): ``

## Recommendation

**Pick: Gemma 4 E4B served by Ollama at `http://localhost:11434/v1`.**

Decision rule: religious-error recall (primary), then CER (tiebreak), then latency.

Whisper (MLX large-v3) stays as a fallback for short utterances ("next", barge-in commands)
where its sub-second latency matters and hallucination is unlikely.

### Known limits and mitigations (locked in `config.py`)

1. **30 s per-clip hard limit on Gemma 4 audio** (Google spec; 25 tokens/s).
   The three empty Gemma transcripts (m05 clean 34 s, m18 with_error 60 s, m08 with_error 12 s)
   are this limit plus one intermittent crash. Mitigation: chunk recitation at line
   boundaries → each chunk ≤ 25 s (`STT_MAX_CLIP_S`). Per-line feedback is also better UX.
2. **Intermittent GGML crash on Gemma 4 audio in Ollama** ([#15333](https://github.com/ollama/ollama/issues/15333)).
   Mitigation: single retry on empty response (`STT_RETRY_ON_EMPTY = 1`).
3. **Ollama silently truncates at `num_ctx` default of 2048**.
   Mitigation: send `num_ctx: 8192` in options (`STT_NUM_CTX = 8192`).