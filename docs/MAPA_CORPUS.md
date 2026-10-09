# Mapa do corpus

Gerado por `tools/mapa_corpus.py` a partir dos `.ts` do aTormenta (mesmos rótulos de Tabela/Fonte/Nome da metadata dos chunks). Não edite à mão: rode o script de novo.

- Registros: 4997 em 105 tabelas
- Fontes: 52
- Nomes em mais de uma Tabela ou Fonte: 160 (dos quais 0 só por grafia diferente da mesma Fonte)

## Fontes

| Fonte | Registros |
|---|---:|
| Tormenta20 - Jogo do Ano | 1186 |
| Herois de Arton | 1060 |
| Compendio T20 | 737 |
| Ameaças de Arton | 646 |
| Deuses de Arton | 393 |
| Dragão Brasil - 199 | 78 |
| Duelo de Dragões | 67 |
| Dragão Brasil | 67 |
| Guia de Deuses Menores | 60 |
| Guia dos Deuses Menores | 60 |
| A Lenda de Ghanor | 54 |
| tormenta20 - jogo do ano | 53 |
| Uma visita a Vectora | 43 |
| Dragão Brasil - 201 | 42 |
| Dragão Brasil - 212 | 40 |
| Tormenta20 - jogo do ano | 38 |
| Dragão Brasil - 227 | 38 |
| Fulgor dos Deuses | 38 |
| Dragão Brasil - 183 | 34 |
| Dragão Brasil - 219 | 28 |
| DB - 228 | 26 |
| DB - 229 | 24 |
| Dragão Brasil - 200 | 22 |
| DB - 227 | 22 |
| Dragão Brasil - 228 | 20 |
| Tormenta20 | 20 |
| Dragão Brasil - 222 | 12 |
| Dragão Brasil - Final Fantasy | 10 |
| Dragão Brasil - 203 | 9 |
| Dragão Brasil - 211 | 6 |
| Dragão Brasil - Dungeon Meshi | 6 |
| Dragão Brasil - 224 | 6 |
| Uma Visita a Vectora | 6 |
| Dragão Brasil - 229 | 5 |
| Dragão Brasil - God of War | 4 |
| Dragão Brasil - God of War Ragnarok | 4 |
| Dragão Brasil - 214 | 3 |
| Dragão Brasil - 204 | 3 |
| Dragão Brasil - 205 | 3 |
| Dragão Brasil - 215 | 3 |
| Dragão Brasil - Zelda | 3 |
| Expedição Escarlate | 3 |
| Dragão Brasil - 223 | 2 |
| Dragão Brasil - 206 | 2 |
| Dragão Brasil - 208 | 2 |
| Dragão Brasil - Culinária Sckharjagar | 2 |
| Dragão Brasil - 220 | 2 |
| Dragão Brasil - 218 | 1 |
| Dragão Brasil - 221 | 1 |
| Dragão Brasil - 209 | 1 |
| Dragão Brasil - 216 | 1 |
| Dragão Brasil - Dragon Age | 1 |

### Mesma Fonte com grafias diferentes

Agrupadas por minúsculas e sem acento; abreviações e palavras diferentes (ex.: `DB` x `Dragão Brasil`, `de` x `dos`) não são detectadas aqui.

- `tormenta20 - jogo do ano`: Tormenta20 - Jogo do Ano · Tormenta20 - jogo do ano · tormenta20 - jogo do ano
- `uma visita a vectora`: Uma Visita a Vectora · Uma visita a Vectora

## Tabelas

## Acessórios

146 registros · exports: `acessorios.ts:accessories`

Fontes: Tormenta20 - Jogo do Ano (65) · Herois de Arton (64) · Dragão Brasil - 228 (6) · Dragão Brasil - 200 (3) · Ameaças de Arton (3) · Dragão Brasil - 214 (2) · Uma visita a Vectora (1) · Dragão Brasil - 218 (1) · Duelo de Dragões (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `price` 100%, `size` 100%, `origin` 100%

- `price`: T$ 3.600 | T$ 3.000 | T$ 9.000
- `size`: Menor | Maior | Médio

## Acessórios Mágicos Maiores

23 registros · exports: `magicos.ts:ACESSORIOS_MAIORES`

Fontes: Compendio T20 (23)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `preco` 100%

- `preco`: T$ 30.000 | T$ 51.000 | T$ 60.000

## Acessórios Mágicos Menores

21 registros · exports: `magicos.ts:ACESSORIOS_MENORES`

Fontes: Compendio T20 (21)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `preco` 100%

- `preco`: T$ 3.000 | T$ 4.500 | T$ 6.000

## Acessórios Mágicos Médios

22 registros · exports: `magicos.ts:ACESSORIOS_MEDIOS`

Fontes: Compendio T20 (22)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `preco` 100%

- `preco`: T$ 10.500 | T$ 15.000 | T$ 16.500

## Acessórios por Grau

1 registros · exports: `magicos.ts:ACESSORIO_POR_GRAU`

Fontes: Compendio T20 (1)

Campos (% preenchido): 


## Alimentos

109 registros · exports: `food.ts:food`

Fontes: Tormenta20 - Jogo do Ano (29) · Tormenta20 (20) · Deuses de Arton (20) · Herois de Arton (14) · Dragão Brasil - Final Fantasy (10) · Ameaças de Arton (7) · Dragão Brasil - Dungeon Meshi (6) · Dragão Brasil - Culinária Sckharjagar (2) · Dragão Brasil (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%, `category` 100%, `cookingDC` 45%, `ingredients` 43%, `cookingCost` 25%

- `price`: T$ 2 | T$ 18 | T$ 6
- `category`: Alimentação | Bebida | Ingrediente

## Alquímicos

86 registros · exports: `alchemys.ts:alchemy`

Fontes: Tormenta20 - Jogo do Ano (30) · Ameaças de Arton (17) · Herois de Arton (17) · Deuses de Arton (13) · Uma visita a Vectora (6) · Dragão Brasil - 200 (2) · Dragão Brasil - 228 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `type` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `type`: Preparados | Catalisadores | Venenos
- `price`: T$ 10 | T$ 50 | T$ 30

## Ameaças

708 registros · exports: `threats.ts:threats`

Fontes: Ameaças de Arton (430) · Deuses de Arton (76) · Tormenta20 - Jogo do Ano (64) · Duelo de Dragões (57) · Fulgor dos Deuses (38) · Dragão Brasil (34) · Uma Visita a Vectora (6) · Expedição Escarlate (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `nd` 100%, `tipo` 100%, `tema` 100%, `tamanho` 100%, `papel` 100%, `origin` 100%, `iniciativa` 100%, `percepcao` 100%, `defesa` 100%, `fort` 100%, `ref` 100%, `von` 100%, `pv` 100%, `deslocamento` 100%, `for` 100%, `des` 100%, `con` 100%, `int` 100%, `sab` 100%, `car` 100%, `tesouro` 100%, `habilidades` 97%, `ataqueCorpoACorpo` 94%, `resistenciaDano` 93%, `image` 79%, `pericias` 69%, `equipamentos` 49%, `pm` 17%, `ataqueDistancia` 17%

- `nd`: 7 | 11 | 15
- `tipo`: Humanoide | Espírito (suraggel) | Morto-vivo
- `tamanho`: Médio | Pequeno | Grande
- `pm`: 81 | 20 | 70

## Animais

23 registros · exports: `animals.ts:animals`

Fontes: Ameaças de Arton (9) · Tormenta20 - Jogo do Ano (8) · Herois de Arton (6)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 30 | T$ 150 | T$ 75

## Aparatos

15 registros · exports: `aparatos.ts:aparatos`

Fontes: Herois de Arton (15)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 450 | T$ 300 | T$ 600

## Armaduras

41 registros · exports: `armors.ts:armors`, `itens.ts:EQUIPAMENTO_ARMADURA`

Fontes: Herois de Arton (14) · Tormenta20 - Jogo do Ano (12) · Compendio T20 (11) · Ameaças de Arton (4)

Campos (% preenchido): `id` 73%, `name` 73%, `type` 73%, `description` 73%, `origin` 73%, `price` 73%, `defenseBonus` 73%, `armorPenalty` 73%, `spaces` 73%, `image` 39%, `min` 27%, `max` 27%, `result` 27%

- `type`: Leve | Pesada | Escudo
- `price`: T$ 5 | T$ 20 | T$ 35

## Armaduras Específicas

13 registros · exports: `magicos.ts:ARMADURAS_ESPECIFICAS`

Fontes: Compendio T20 (13)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `preco` 100%

- `preco`: T$ 30.000 | T$ 36.000 | T$ 45.000

## Armaduras Mágicas

26 registros · exports: `magicos.ts:ARMADURAS_MAGICAS`

Fontes: Compendio T20 (26)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `encanto` 100%, `efeito` 100%


## Armaduras Superiores

12 registros · exports: `itens.ts:SUPERIOR_ARMADURA`

Fontes: Compendio T20 (12)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%


## Armas

157 registros · exports: `itens.ts:EQUIPAMENTO_ARMA`, `weapons.ts:weapons`

Fontes: Compendio T20 (48) · Tormenta20 - Jogo do Ano (44) · Herois de Arton (43) · Ameaças de Arton (16) · Duelo de Dragões (2) · Dragão Brasil - 199 (1) · Dragão Brasil - 205 (1) · Dragão Brasil - 219 (1) · Deuses de Arton (1)

Campos (% preenchido): `id` 69%, `name` 69%, `description` 69%, `origin` 69%, `purpose` 69%, `proficiency` 69%, `grip` 69%, `price` 69%, `damage` 69%, `critical` 69%, `range` 69%, `type` 69%, `spaces` 69%, `image` 38%, `min` 31%, `max` 31%, `result` 31%

- `proficiency`: Exótica | Simples | Marcial
- `grip`: Uma Mão | Leve | Duas Mãos
- `price`: T$ 750 | T$ 50 | T$ 75
- `damage`: 1d6 | 1d10 | 1d12
- `critical`: 19 | x4 | 19/x3
- `type`: Corte | Perfuração | Essência

## Armas Específicas

18 registros · exports: `magicos.ts:ARMAS_ESPECIFICAS`

Fontes: Compendio T20 (18)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `preco` 100%

- `preco`: T$ 30.000 | T$ 45.000 | T$ 50.000

## Armas Mágicas

29 registros · exports: `magicos.ts:ARMAS_MAGICAS`

Fontes: Compendio T20 (29)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `encanto` 100%, `efeito` 100%


## Armas Mágicas Específicas

25 registros · exports: `magicarmor.ts:specificWeapons`

Fontes: Tormenta20 - Jogo do Ano (13) · Herois de Arton (10) · Ameaças de Arton (1) · Deuses de Arton (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `price` 100%, `origin` 100%

- `price`: 150.000 | 50.000 | 63.000

## Armas Superiores

15 registros · exports: `itens.ts:SUPERIOR_ARMA`

Fontes: Compendio T20 (15)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%


## Artefatos

45 registros · exports: `artifacts.ts:artifacts`

Fontes: Dragão Brasil - 183 (10) · Dragão Brasil - 222 (10) · Herois de Arton (8) · Deuses de Arton (6) · Tormenta20 - Jogo do Ano (5) · Dragão Brasil - 204 (2) · Ameaças de Arton (2) · Duelo de Dragões (1) · Dragão Brasil (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `image` 27%


## Atributos

6 registros · exports: `attributes.ts:attributes`

Fontes: Compendio T20 (6)

Campos (% preenchido): `id` 100%, `name` 100%, `abbreviation` 100%, `icon` 100%, `description` 100%


## Atributos de Objetos

1 registros · exports: `rules.tsx:objectStats`

Fontes: Compendio T20 (1)

Campos (% preenchido): 


## Aventuras

70 registros · exports: `adventures.ts:adventures`

Fontes: Compendio T20 (70)

Campos (% preenchido): `id` 100%, `name` 100%, `theme` 100%, `image` 100%, `summary` 100%, `sections` 100%


## Categorias de Equipamento

23 registros · exports: `equipamentos.ts:equipmentCategories`, `itens.ts:EQUIPAMENTO_CATEGORIAS`

Fontes: Compendio T20 (23)

Campos (% preenchido): `id` 87%, `title` 87%, `description` 87%, `icon` 87%, `color` 87%, `href` 87%, `min` 13%, `max` 13%, `label` 13%


## Categorias de Item Mágico

5 registros · exports: `itensmagicos.ts:equipmentCategories`, `magicos.ts:MAGICO_CATEGORIAS`

Fontes: Compendio T20 (5)

Campos (% preenchido): `min` 60%, `max` 60%, `label` 60%, `id` 40%, `title` 40%, `description` 40%, `icon` 40%, `color` 40%, `href` 40%


## Categorias de Item Superior

3 registros · exports: `itens.ts:SUPERIOR_CATEGORIAS`

Fontes: Compendio T20 (3)

Campos (% preenchido): `min` 100%, `max` 100%, `label` 100%


## Categorias de Poder

26 registros · exports: `power-categories.ts:powerCategories`

Fontes: tormenta20 - jogo do ano (19) · Dragão Brasil (3) · Herois de Arton (3) · Deuses de Arton (1)

Campos (% preenchido): `id` 100%, `name` 100%, `slug` 100%, `description` 100%, `origin` 100%


## Chefes

86 registros · exports: `bosses.ts:bosses`

Fontes: Compendio T20 (86)

Campos (% preenchido): `id` 100%, `name` 100%, `image` 100%, `tipo` 100%, `nd` 100%, `historia` 100%, `tamanho` 100%, `iniciativa` 100%, `percepcao` 100%, `defesa` 100%, `fort` 100%, `ref` 100%, `von` 100%, `pv` 100%, `deslocamento` 100%, `pm` 100%, `for` 100%, `des` 100%, `con` 100%, `int` 100%, `sab` 100%, `car` 100%, `tesouro` 100%, `habilidades` 99%, `dicas` 95%, `ataqueCorpoACorpo` 93%, `pericias` 92%, `resistenciaDano` 91%, `equipamentos` 71%, `ataqueDistancia` 12%

- `tipo`: Monstro Enorme | Humanoide | Espírito
- `nd`: 12 | 7 | 15
- `tamanho`: Enorme | Médio | Grande
- `pm`: 0 | 21 | 120

## Classes

39 registros · exports: `classes.ts:classes`

Fontes: Herois de Arton (15) · tormenta20 - jogo do ano (14) · A Lenda de Ghanor (2) · Dragão Brasil - 199 (2) · Dragão Brasil - 222 (2) · Dragão Brasil - 223 (2) · Dragão Brasil - 211 (1) · Deuses de Arton (1)

Campos (% preenchido): `id` 100%, `name` 100%, `origin` 100%, `image` 100%, `powersUrl` 100%, `description` 100%, `characteristics` 100%, `skills` 100%, `proficiency` 100%, `abilities` 100%, `levelProgression` 100%, `famousExamples` 38%, `extras` 36%

- `skills`: {"mandatory": ["Misticismo (Int)", "Vontade (Sab)"], "optional": {"sk… | {"mandatory": ["Luta (For) ou Pontaria (Des)", "Fortitude (Con)"], "o… | {"mandatory": ["Fortitude (Con)", "Luta (For)"], "optional": {"skills…
- `proficiency`: Nenhuma | Armas marciais e escudos | Armas marciais
- `levelProgression`: [{"level": 1, "abilities": "Magias (1º círculo), tradição arcana"}, {… | [{"level": 1, "abilities": "Ataque disciplinado (+1d6)"}, {"level": 2… | [{"level": 1, "abilities": "Caminhos do arcanista, magias (1º círculo…

## Complicações

54 registros · exports: `complicacoes.ts:complications`

Fontes: Herois de Arton (54)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `efeito` 100%


## Complicações de Idade

19 registros · exports: `rules.tsx:ageComplications`

Fontes: Compendio T20 (19)

Campos (% preenchido): `name` 100%, `effect` 100%


## Condições

56 registros · exports: `conditions.ts:conditions`

Fontes: Tormenta20 - Jogo do Ano (35) · Dragão Brasil - 219 (21)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `efeito` 59%


## Deuses

92 registros · exports: `gods.ts:gods`

Fontes: Guia de Deuses Menores (60) · Tormenta20 - Jogo do Ano (20) · Compendio T20 (8) · Dragão Brasil (4)

Campos (% preenchido): `id` 100%, `name` 100%, `image` 100%, `status` 100%, `sacredSymbol` 100%, `channelEnergy` 100%, `preferredWeapon` 100%, `history` 100%, `beliefs` 100%, `devotees` 100%, `obligationsRestrictions` 100%, `grantedPowers` 98%, `subtitle` 91%, `rank` 68%, `otherNames` 32%, `areasOfInfluence` 22%, `significantColors` 22%, `motto` 22%, `motivations` 22%, `relationships` 22%, `churchAndClergy` 22%


## Dificuldades de Teste

7 registros · exports: `rules.tsx:difficulties`

Fontes: Compendio T20 (7)

Campos (% preenchido): `task` 100%, `cd` 100%, `example` 100%


## Dinheiro Inicial

20 registros · exports: `equipamentos.ts:initialMoneyTable`

Fontes: Compendio T20 (20)

Campos (% preenchido): `level` 100%, `money` 100%

- `level`: 1 | 2 | 3

## Distinções

70 registros · exports: `distinctions.ts:distinctions`

Fontes: Herois de Arton (36) · Deuses de Arton (23) · Dragão Brasil - 215 (3) · Dragão Brasil (3) · Dragão Brasil - 206 (2) · Duelo de Dragões (1) · Dragão Brasil - 205 (1) · Dragão Brasil - 208 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `origin` 100%, `image` 100%, `introduction` 100%, `admission` 100%, `mark` 100%, `powers` 100%, `extras` 46%


## Dádivas de Aharadak

5 registros · exports: `dadivas-aharadak.ts:aharadak`

Fontes: Ameaças de Arton (5)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 54.000 | T$ 27.000 | T$ 33.000

## Encantamentos Amaldiçoados

32 registros · exports: `curseds.ts:enchantments`

Fontes: Herois de Arton (32)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `type` 100%

- `type`: Armas | Armaduras e Escudos

## Encantamentos de Acessórios

8 registros · exports: `acessorios.ts:enchantments`

Fontes: Herois de Arton (8)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%


## Encantamentos de Armaduras

45 registros · exports: `magicarmor.ts:enchantments`

Fontes: Tormenta20 - Jogo do Ano (25) · Herois de Arton (20)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%


## Encantamentos de Esotéricos

26 registros · exports: `magicesoterics.ts:enchantments`

Fontes: Herois de Arton (26)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%


## Encantamentos de Itens Mágicos

50 registros · exports: `magics.ts:enchantments`

Fontes: Tormenta20 - Jogo do Ano (28) · Herois de Arton (22)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%


## Equipamentos

75 registros · exports: `gear.ts:gear`

Fontes: Herois de Arton (25) · Tormenta20 - Jogo do Ano (17) · Uma visita a Vectora (14) · Deuses de Arton (13) · Ameaças de Arton (4) · Dragão Brasil - 183 (1) · Dragão Brasil - 228 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 150 | T$ 300 | T$ 90

## Esotéricos

39 registros · exports: `esoterics.ts:esoteric`, `itens.ts:EQUIPAMENTO_ESOTER`

Fontes: Tormenta20 - Jogo do Ano (10) · Compendio T20 (10) · Deuses de Arton (9) · Herois de Arton (4) · Ameaças de Arton (3) · Dragão Brasil - 228 (2) · Duelo de Dragões (1)

Campos (% preenchido): `id` 74%, `name` 74%, `description` 74%, `origin` 74%, `price` 74%, `spaces` 74%, `min` 26%, `max` 26%, `result` 26%

- `price`: T$ 300 | T$ 250 | T$ 750

## Esotéricos Mágicos Específicos

4 registros · exports: `magicesoterics.ts:specificWeapons`

Fontes: Herois de Arton (4)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `price` 100%, `origin` 100%

- `price`: 27.000 | 150.000 | 60.000

## Esotéricos Superiores

10 registros · exports: `itens.ts:SUPERIOR_ESOTER`

Fontes: Compendio T20 (10)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%


## Faixas Etárias

7 registros · exports: `rules.tsx:ageGroups`

Fontes: Compendio T20 (7)

Campos (% preenchido): `name` 100%, `age` 100%, `modifiers` 100%


## Ferramentas

16 registros · exports: `tools.ts:tool`

Fontes: Tormenta20 - Jogo do Ano (8) · Herois de Arton (6) · Dragão Brasil - 183 (1) · Deuses de Arton (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 75 | T$ 10 | T$ 50

## Instrumentos Musicais

18 registros · exports: `music.ts:music`

Fontes: Herois de Arton (11) · Tormenta20 - Jogo do Ano (4) · Dragão Brasil - 209 (1) · Dragão Brasil - 228 (1) · Deuses de Arton (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 19000 | T$ 175 | T$ 35

## Itens Diversos

49 registros · exports: `itens.ts:DIVERSO`

Fontes: Compendio T20 (49)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%


## Itens Litúrgicos

35 registros · exports: `liturgical.ts:liturgico`

Fontes: Deuses de Arton (35)

Campos (% preenchido): `id` 100%, `name` 100%, `type` 100%, `description` 100%, `origin` 100%, `price` 100%

- `type`: Acessório Maior | Acessório menor | Arma específica menor
- `price`: T$ 37000 | T$ 45000 | T$ 9000

## Itens Mágicos Específicos

49 registros · exports: `magics.ts:specificWeapons`

Fontes: Tormenta20 - Jogo do Ano (18) · Herois de Arton (17) · Dragão Brasil - 183 (7) · Dragão Brasil - 228 (2) · Ameaças de Arton (2) · Dragão Brasil (1) · Dragão Brasil - 221 (1) · Duelo de Dragões (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `price` 100%, `origin` 100%

- `price`: 30.000 | 60.000 | 135.000

## Magias

264 registros · exports: `spells.ts:spells`

Fontes: Tormenta20 - Jogo do Ano (198) · Deuses de Arton (29) · Herois de Arton (22) · Ameaças de Arton (7) · Dragão Brasil - 219 (6) · Dragão Brasil - 199 (1) · Dragão Brasil - 228 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `type` 100%, `school` 100%, `circle` 100%, `execution` 100%, `range` 100%, `target` 100%, `duration` 100%, `resistance` 100%, `description` 100%, `origin` 100%, `enhancements` 93%

- `type`: Divina | Arcana | Universal
- `school`: Transmutação | Encantamento | Abjuração
- `circle`: 1 | 2 | 5

## Melhorias de Item

58 registros · exports: `superior_items.ts:improvements`

Fontes: Tormenta20 - Jogo do Ano (29) · Herois de Arton (12) · Uma visita a Vectora (5) · Deuses de Arton (5) · Dragão Brasil - 183 (3) · Ameaças de Arton (2) · Duelo de Dragões (1) · Dragão Brasil (1)

Campos (% preenchido): `id` 100%, `name` 100%, `effect` 100%, `category` 100%, `description` 100%, `origin` 100%

- `category`: ["Vestuário"] | ["Ferramenta", "Vestuário", "Aventura"] | ["Armadura", "Escudo"]

## Montarias

54 registros · exports: `mounts.ts:mounts`

Fontes: Ameaças de Arton (41) · Tormenta20 - Jogo do Ano (4) · Deuses de Arton (4) · Duelo de Dragões (1) · Dragão Brasil - 205 (1) · Dragão Brasil - 208 (1) · Dragão Brasil - 212 (1) · Dragão Brasil (1)

Campos (% preenchido): `id` 100%, `name` 100%, `size` 100%, `description` 100%, `origin` 100%, `benefits` 100%, `extra` 4%

- `size`: Grande | Enorme | Médio / Pequeno

## Nota de Dificuldades

1 registros · exports: `rules.tsx:difficultiesNote`

Fontes: Compendio T20 (1)

Campos (% preenchido): 


## Nota de Tamanho de Criaturas

1 registros · exports: `caracteristicas.ts:creatureSizeTableFootnote`

Fontes: Compendio T20 (1)

Campos (% preenchido): 


## Objetivos Heroicos

7 registros · exports: `rules.tsx:heroicGoals`

Fontes: Compendio T20 (7)

Campos (% preenchido): `name` 100%, `description` 100%, `benefit` 100%, `penalty` 100%, `conclusion` 100%


## Organizações

20 registros · exports: `organizations.ts:organizations`

Fontes: Compendio T20 (20)

Campos (% preenchido): `id` 100%, `name` 100%, `summary` 100%, `lore` 100%, `membros` 100%, `comoUsar` 100%, `mecanica` 100%, `image` 30%


## Origens

89 registros · exports: `origins.ts:origins`

Fontes: Tormenta20 - Jogo do Ano (35) · Herois de Arton (30) · A Lenda de Ghanor (18) · Dragão Brasil - God of War (4) · Dragão Brasil - 214 (1) · Dragão Brasil (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `items` 100%, `benefits` 100%, `uniquePower` 100%, `source` 100%


## Papéis no Grupo

9 registros · exports: `rules.tsx:groupRoles`

Fontes: Compendio T20 (9)

Campos (% preenchido): `name` 100%, `description` 100%, `benefit` 100%


## Parceiros

57 registros · exports: `partners.ts:partners`

Fontes: Ameaças de Arton (19) · Deuses de Arton (13) · Tormenta20 - Jogo do Ano (12) · Dragão Brasil - 229 (5) · Dragão Brasil - 228 (3) · Uma visita a Vectora (2) · Dragão Brasil - 220 (1) · Dragão Brasil - 216 (1) · Dragão Brasil - 204 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `benefits` 100%, `category` 19%, `archetype` 14%

- `category`: especifico | arquetipo

## Perigos

41 registros · exports: `dangers.ts:dangers`

Fontes: Ameaças de Arton (27) · Tormenta20 - Jogo do Ano (14)

Campos (% preenchido): `id` 100%, `name` 100%, `content` 100%, `category` 100%

- `category`: Tormenta20 - Jogo do Ano | Ameaças de Arton

## Perícias

29 registros · exports: `pericias.ts:skills`

Fontes: Compendio T20 (29)

Campos (% preenchido): `id` 100%, `name` 100%, `attribute` 100%, `trainedOnly` 100%, `armorPenalty` 100%, `description` 100%, `functions` 79%


## Poderes (Arcanista)

52 registros · exports: `powers-arcanista.ts:powersArcanista`

Fontes: Tormenta20 - jogo do ano (21) · Herois de Arton (20) · A Lenda de Ghanor (6) · Dragão Brasil - 212 (3) · Dragão Brasil - 200 (2)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 81%

- `prerequisite`: Mago (A Lenda de Ghanor), treinado em Conhecimento. | Mago (A Lenda de Ghanor) | Mago (A Lenda de Ghanor), Raio Arcano.

## Poderes (Bardo)

47 registros · exports: `powers-bardo.ts:powersBardo`

Fontes: Tormenta20 - Jogo do Ano (20) · Herois de Arton (20) · A Lenda de Ghanor (4) · Dragão Brasil - 212 (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 55%

- `prerequisite`: Int 2, 6° nível de bardo. | Esgrima Mágica, 10º nível de bardo. | 6º nível de bardo.

## Poderes (Bucaneiro)

48 registros · exports: `powers-bucaneiro.ts:powersBucaneiro`

Fontes: Herois de Arton (21) · Tormenta20 - Jogo do Ano (19) · A Lenda de Ghanor (4) · Dragão Brasil - 212 (3) · Dragão Brasil - 200 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 65%

- `prerequisite`: Car 3. | Flagelo dos Mares. | Car 1, 6º nível de bucaneiro.

## Poderes (Bárbaro)

44 registros · exports: `powers-barbaro.ts:powersBarbaro`

Fontes: Tormenta20 - Jogo do Ano (20) · Herois de Arton (20) · Dragão Brasil - 212 (3) · A Lenda de Ghanor (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 57%

- `prerequisite`: 5º nível de bárbaro, treinado em Vontade. | For 1. | Alma de Bronze

## Poderes (Cavaleiro)

46 registros · exports: `powers-cavaleiro.ts:powersCavaleiro`

Fontes: Tormenta20 - Jogo do Ano (20) · Herois de Arton (20) · Dragão Brasil - 212 (3) · Dragão Brasil - 200 (2) · A Lenda de Ghanor (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 39%

- `prerequisite`: 6º nível de cavaleiro. | 12º nível de cavaleiro. | Título, 14º nível de cavaleiro.

## Poderes (Caçador)

53 registros · exports: `powers-cacador.ts:powersCacador`

Fontes: Tormenta20 - Jogo do Ano (23) · Herois de Arton (22) · Dragão Brasil - 211 (5) · Dragão Brasil - 212 (2) · A Lenda de Ghanor (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 58%

- `prerequisite`: Armadilheiro, dois poderes de armadilha. | Des 2 | Um poder de armadilha, 5º nível de caçador.

## Poderes (Clérigo)

43 registros · exports: `powers-clerigo.ts:powersClerigo`

Fontes: Herois de Arton (20) · Tormenta20 - Jogo do Ano (18) · A Lenda de Ghanor (3) · Dragão Brasil - 212 (2)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 60%

- `prerequisite`: Canalizar Energia | Car 1, 5º nível de clérigo. | Fiéis

## Poderes (Druida)

53 registros · exports: `powers-druida.ts:powersDruida`

Fontes: Tormenta20 - Jogo do Ano (22) · Herois de Arton (22) · Dragão Brasil (6) · Dragão Brasil - 212 (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 75%

- `prerequisite`: Car 1, treinado em Adestramento. | Companheiro Animal, 6º nível de druida. | Companheiro Animal, 18º nível de druida.

## Poderes (Frade)

29 registros · exports: `powers-frade.ts:powersFrade`

Fontes: Deuses de Arton (29)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 55%

- `prerequisite`: 5º nível de frade. | 10º nível de frade. | 5º nível de frade, devoto de um deus maior.

## Poderes (Guerreiro)

49 registros · exports: `powers-guerreiro.ts:powersGuerreiro`

Fontes: Herois de Arton (21) · Tormenta20 - Jogo do Ano (19) · A Lenda de Ghanor (6) · Dragão Brasil - 212 (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 65%

- `prerequisite`: 5º nível de soldado. | Especialista em Armadura, Especialização em Arma. | Treinado em Luta.

## Poderes (Inventor)

52 registros · exports: `powers-inventor.ts:powersInventor`

Fontes: Tormenta20 - Jogo do Ano (30) · Herois de Arton (20) · Dragão Brasil - 212 (2)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 94%

- `prerequisite`: treinado em Ofício (alquimista). | Balística. | Alquimista Iniciado.

## Poderes (Ladino)

45 registros · exports: `powers-ladino.ts:powersLadino`

Fontes: tormenta20 - jogo do ano (20) · Herois de Arton (20) · Dragão Brasil - 212 (3) · A Lenda de Ghanor (2)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 80%

- `prerequisite`: Car 1, treinado em Enganação. | Camaleão, 11º nível de ladino. | 5º nível de ladino

## Poderes (Lutador)

46 registros · exports: `powers-lutador.ts:powersLutador`

Fontes: Tormenta20 - Jogo do Ano (23) · Herois de Arton (20) · Dragão Brasil - 212 (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 54%

- `prerequisite`: Int 1, Lutador de Chão, 4º nível de lutador. | 8º nível de lutador. | Chave, 8º nível de lutador.

## Poderes (Místico)

47 registros · exports: `powers-mistico.ts:powersMistico`

Fontes: Dragão Brasil - 199 (47)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 85%

- `prerequisite`: 12º nível de místico, Afinidade Expandida. | Afinidade (terra). | 4º nível de místico, Afinidade (terra).

## Poderes (Nobre)

41 registros · exports: `powers-nobre.ts:powersNobre`

Fontes: Herois de Arton (20) · Tormenta20 - Jogo do Ano (18) · Dragão Brasil - 212 (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 73%

- `prerequisite`: 8º nível de nobre. | 6º nível de nobre. | Int 1, treinado em Guerra, 6º nível de nobre.

## Poderes (Paladino)

47 registros · exports: `powers-paladino.ts:powersPaladino`

Fontes: Tormenta20 - Jogo do Ano (22) · Herois de Arton (22) · Dragão Brasil - 212 (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 47%

- `prerequisite`: devoto de uma divindade (exceto Lena e Marah). | 14º nível de paladino. | 10º nível de paladino.

## Poderes (Samurai)

68 registros · exports: `powers-samurai.ts:powersSamurai`

Fontes: Dragão Brasil - 201 (42) · Dragão Brasil - 199 (26)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 88%

- `prerequisite`: 10º nível de samurai, arma ancestral profana ou sagrada. | 10º nível de samurai, arma ancestral dançarina. | arma ancestral macabra.

## Poderes (Treinador)

21 registros · exports: `powers-treinador.ts:powersTreinador`

Fontes: Herois de Arton (21)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 33%

- `prerequisite`: 11º nível de treinador | 5º nível de treinador. | Domador Cativante, 17º nível de treinador.

## Poderes (Vampiro)

10 registros · exports: `powers-vampiro.ts:powersVampiro`

Fontes: Dragão Brasil (10)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 20%

- `prerequisite`: Presença Majestosa.

## Poderes Concedidos

230 registros · exports: `powers-gerais-concedido.ts:powersGeraisConcedido`

Fontes: Deuses de Arton (78) · Tormenta20 - Jogo do Ano (72) · Guia dos Deuses Menores (60) · Dragão Brasil - 183 (10) · Dragão Brasil - 203 (9) · Dragão Brasil - 228 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 0%

- `prerequisite`: habilidade de classe Magias.

## Poderes Gerais

105 registros · exports: `powers-gerais.ts:powersGerais`

Fontes: Tormenta20 - Jogo do Ano (40) · Dragão Brasil - 227 (38) · Herois de Arton (25) · Ameaças de Arton (2)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 96%

- `prerequisite`: Des 1 | Estilo de Duas Armas. | For 1, Estilo de Arremesso

## Poderes da Tormenta

28 registros · exports: `powers-gerais-tormenta.ts:powersGeraisTormenta`

Fontes: Tormenta20 - Jogo do Ano (22) · Herois de Arton (6)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 39%

- `prerequisite`: outro poder da Tormenta. | quatro outros poderes da Tormenta. | Dentes Afiados.

## Poderes de Destino

73 registros · exports: `powers-gerais-destino.ts:powersGeraisDestino`

Fontes: Tormenta20 - Jogo do Ano (20) · Deuses de Arton (20) · Herois de Arton (15) · Dragão Brasil - 200 (12) · Ameaças de Arton (3) · Dragão Brasil - 228 (2) · Dragão Brasil - 199 (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 85%

- `prerequisite`: Des 2. | 6º nível de personagem. | Car 1.

## Poderes de Grupo

20 registros · exports: `powers-gerais-grupo.ts:powersGeraisGrupo`

Fontes: Herois de Arton (20)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 25%

- `prerequisite`: treinado em Luta ou Pontaria | treinado em Iniciativa | Exército de Um Grupo Só, outro poder de grupo

## Poderes de Magia

22 registros · exports: `powers-gerais-magia.ts:powersGeraisMagia`

Fontes: Herois de Arton (14) · Tormenta20 - Jogo do Ano (8)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `prerequisite` 50%

- `prerequisite`: treinado em Misticismo ou Religião, 8º nível de personagem. | habilidade de classe Magias, treinado em Ofício (escriba). | lançar magias de 2º círculo.

## Poderes de Raça

77 registros · exports: `powers-gerais-raca.ts:powersGeraisRaca`

Fontes: Herois de Arton (77)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `prerequisite` 100%, `origin` 100%

- `prerequisite`: Qareen | Anão, Hobgoblin | arma natural fornecida por uma habilidade de raça

## Poções

38 registros · exports: `magicos.ts:POCOES`

Fontes: Compendio T20 (38)

Campos (% preenchido): `min` 100%, `max` 100%, `result` 100%, `preco` 100%

- `preco`: T$ 30 | T$ 120 | T$ 270

## Preços de Materiais

17 registros · exports: `superior_items.ts:materialPrices`

Fontes: Ameaças de Arton (8) · Tormenta20 - Jogo do Ano (7) · Dragão Brasil - 183 (2)

Campos (% preenchido): `material` 100%, `Arma` 100%, `Armadura Leve` 100%, `Armadura Pesada` 100%, `Escudo` 100%, `Esotéricos` 100%, `description` 100%, `origin` 100%, `description_arma` 88%, `description_esoterico` 88%, `description_armadura` 82%, `description_escudo` 53%


## Preços de Melhorias

4 registros · exports: `superior_items.ts:priceImprovements`

Fontes: Compendio T20 (4)

Campos (% preenchido): `level` 100%, `priceIncrease` 100%, `cdIncrease` 100%

- `level`: 1 | 2 | 3

## Progressão de Dano

8 registros · exports: `weapons.ts:damageProgressionTable`

Fontes: Compendio T20 (8)

Campos (% preenchido): `0` 100%, `1` 100%, `2` 100%, `3` 100%, `4` 100%, `5` 100%


## Raças

74 registros · exports: `races.ts:races`

Fontes: Ameaças de Arton (29) · Tormenta20 - jogo do ano (17) · A Lenda de Ghanor (6) · Dragão Brasil - 224 (6) · Herois de Arton (5) · Dragão Brasil - God of War Ragnarok (4) · Dragão Brasil - Zelda (3) · Dragão Brasil - 220 (1) · Duelo de Dragões (1) · Dragão Brasil - Dragon Age (1) · Dragão Brasil (1)

Campos (% preenchido): `id` 100%, `name` 100%, `origin` 100%, `image` 100%, `description` 100%, `abilities` 100%, `attributeModifiers` 100%, `longevidade` 49%, `devotos` 49%, `extra` 9%

- `attributeModifiers`: [{"attribute": "car", "modifier": -2}, {"description": "Mutações pode… | [{"attribute": "con", "modifier": 2}, {"attribute": "int", "modifier"… | [{"attribute": "sab", "modifier": 2}, {"attribute": "des", "modifier"…

## Regras

12 registros · exports: `rules.tsx:ruleSections`

Fontes: Compendio T20 (12)

Campos (% preenchido): `id` 100%, `title` 100%, `content` 100%


## Regreiro (Perguntas e Respostas)

72 registros · exports: `regreiro.ts:regreiroQAs`

Fontes: DB - 228 (26) · DB - 229 (24) · DB - 227 (22)

Campos (% preenchido): `id` 100%, `question` 100%, `answer` 100%, `magazineNumber` 100%


## Riquezas

13 registros · exports: `magicos.ts:RIQUEZAS`

Fontes: Compendio T20 (13)

Campos (% preenchido): `menor` 100%, `media` 100%, `maior` 100%, `valor` 100%, `exemplos` 100%


## Serviços

50 registros · exports: `services.ts:services`

Fontes: Herois de Arton (22) · Uma visita a Vectora (14) · Tormenta20 - Jogo do Ano (11) · Deuses de Arton (3)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 2.000 | T$ 200 | T$ 250

## Situações Especiais de Combate

1 registros · exports: `rules.tsx:specialSituations`

Fontes: Compendio T20 (1)

Campos (% preenchido): 


## Tamanho de Criaturas

6 registros · exports: `caracteristicas.ts:creatureSizeTable`

Fontes: Compendio T20 (6)

Campos (% preenchido): `category` 100%, `examples` 100%, `spaceAndReach` 100%, `stealthAndManeuverModifier` 100%

- `category`: Minúsculo | Pequeno | Médio

## Tesouros

22 registros · exports: `tesouros.ts:tesouros`

Fontes: Compendio T20 (22)

Campos (% preenchido): `nd` 100%, `dinheiro` 100%, `itens` 100%

- `nd`: 1/4 | 1/2 | 1

## Testes Estendidos

3 registros · exports: `rules.tsx:extendedTests`

Fontes: Compendio T20 (3)

Campos (% preenchido): `successes` 100%, `complexity` 100%, `example` 100%


## Vestuário

62 registros · exports: `clothing.ts:clothing`

Fontes: Herois de Arton (24) · Tormenta20 - Jogo do Ano (21) · Deuses de Arton (11) · Ameaças de Arton (5) · Uma visita a Vectora (1)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 300 | T$ 1 | T$ 5

## Veículos

9 registros · exports: `vehicles.ts:vehicles`

Fontes: Herois de Arton (5) · Tormenta20 - Jogo do Ano (4)

Campos (% preenchido): `id` 100%, `name` 100%, `description` 100%, `origin` 100%, `price` 100%, `spaces` 100%

- `price`: T$ 200 | T$ 150 | T$ 500

## Nomes em mais de uma Tabela ou Fonte

`só grafia` = a repetição some ao normalizar a Fonte.

| Nome normalizado | Só grafia? | Onde aparece (Tabela > Fonte) |
|---|---|---|
| a espada-deus |  | Artefatos > Tormenta20 - Jogo do Ano; Deuses > Guia de Deuses Menores |
| abencoado |  | Condições > Dragão Brasil - 219; Encantamentos de Armaduras > Tormenta20 - Jogo do Ano |
| acessorios |  | Categorias de Equipamento > Compendio T20; Categorias de Item Mágico > Compendio T20 |
| acido |  | Alquímicos > Tormenta20 - Jogo do Ano; Perigos > Tormenta20 - Jogo do Ano |
| acquarella |  | Ameaças > Dragão Brasil; Montarias > Dragão Brasil - 208 |
| acrobatico |  | Encantamentos de Armaduras > Tormenta20 - Jogo do Ano; Poderes de Destino > Tormenta20 - Jogo do Ano |
| agua benta |  | Alquímicos > Deuses de Arton; Equipamentos > Tormenta20 - Jogo do Ano |
| agulha |  | Armas > Dragão Brasil - 219; Melhorias de Item > Dragão Brasil |
| ajudante |  | Encantamentos de Acessórios > Herois de Arton; Parceiros > Tormenta20 - Jogo do Ano |
| alquimista de batalha |  | Poderes (Inventor) > Tormenta20 - Jogo do Ano; Serviços > Herois de Arton |
| amaldicoados |  | Categorias de Equipamento > Compendio T20; Categorias de Item Mágico > Compendio T20 |
| ambidestria |  | Poderes (Caçador) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| arcanista |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| areia movedica |  | Perigos > Ameaças de Arton; Perigos > Tormenta20 - Jogo do Ano |
| arqueiro |  | Poderes (Caçador) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| aspecto de allihanna |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| aspecto de kallyadranoch |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| aspecto de khalmyr |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| aspecto de lin-wu |  | Ameaças > Deuses de Arton; Montarias > Deuses de Arton |
| aspecto de marah |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| aspecto de valkaria |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| aumento de atributo |  | Poderes (Arcanista) > Tormenta20 - jogo do ano; Poderes (Bardo) > Tormenta20 - Jogo do Ano; Poderes (Bucaneiro) > Tormenta20 - Jogo do Ano; Poderes (Bárbaro) > Tormenta20 - Jogo do Ano; Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano; Poderes (Caçador) > Tormenta20 - Jogo do Ano; Poderes (Clérigo) > Tormenta20 - Jogo do Ano; Poderes (Druida) > Tormenta20 - Jogo do Ano; Poderes (Frade) > Deuses de Arton; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano; Poderes (Inventor) > Tormenta20 - Jogo do Ano; Poderes (Ladino) > tormenta20 - jogo do ano; Poderes (Lutador) > Tormenta20 - Jogo do Ano; Poderes (Místico) > Dragão Brasil - 199; Poderes (Nobre) > Tormenta20 - Jogo do Ano; Poderes (Paladino) > Tormenta20 - Jogo do Ano; Poderes (Treinador) > Herois de Arton |
| autoridade eclesiastica |  | Poderes (Clérigo) > Tormenta20 - Jogo do Ano; Poderes (Frade) > Deuses de Arton |
| autoridade feudal |  | Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano; Poderes (Nobre) > Tormenta20 - Jogo do Ano |
| avatar de aharadak |  | Ameaças > Ameaças de Arton; Ameaças > Deuses de Arton |
| avatar de kallyadranoch |  | Ameaças > Ameaças de Arton; Ameaças > Deuses de Arton |
| baleote |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| barbaro |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| bardo |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| batedor |  | Origens > Tormenta20 - Jogo do Ano; Serviços > Herois de Arton |
| brontoterio |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| bruxo da tormenta |  | Ameaças > Ameaças de Arton; Distinções > Herois de Arton |
| bucaneiro |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| bufalo-de-guerra |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| bulette |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| cacador |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| canto da sereia |  | Poderes (Bardo) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| cao de caca |  | Animais > Tormenta20 - Jogo do Ano; Montarias > Tormenta20 - Jogo do Ano |
| capanga |  | Ameaças > Ameaças de Arton; Origens > Tormenta20 - Jogo do Ano |
| capitao do conclave pirata |  | Ameaças > Ameaças de Arton; Distinções > Herois de Arton |
| capivara |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| cavaleiro |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| cavalo |  | Animais > Tormenta20 - Jogo do Ano; Montarias > Tormenta20 - Jogo do Ano |
| cavalo de guerra |  | Ameaças > Ameaças de Arton; Animais > Tormenta20 - Jogo do Ano |
| cavalo de namalkah |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| cavalo esqueleto |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| cavalo glacial |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| centuriao |  | Ameaças > Ameaças de Arton; Distinções > Dragão Brasil - 215 |
| chapeu-preto |  | Ameaças > Ameaças de Arton; Distinções > Herois de Arton |
| chefe de gangue |  | Ameaças > Ameaças de Arton; Poderes (Ladino) > Herois de Arton |
| clerigo |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| cocatriz-real |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| companheiro animal |  | Poderes (Caçador) > Tormenta20 - Jogo do Ano; Poderes (Druida) > Tormenta20 - Jogo do Ano |
| comunhao vital |  | Poderes (Clérigo) > Tormenta20 - Jogo do Ano; Poderes (Frade) > Deuses de Arton |
| conhecimento magico |  | Poderes (Arcanista) > Tormenta20 - jogo do ano; Poderes (Clérigo) > Tormenta20 - Jogo do Ano; Poderes (Frade) > Deuses de Arton |
| corcel de comando |  | Ameaças > Ameaças de Arton; Montarias > Duelo de Dragões |
| corcel de kally |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| corcel do deserto |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| curandeiro |  | Origens > Tormenta20 - Jogo do Ano; Serviços > Tormenta20 - Jogo do Ano |
| dai-kabuto |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| deinonico |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| destruidor |  | Parceiros > Tormenta20 - Jogo do Ano; Poderes (Bárbaro) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| diligente |  | Melhorias de Item > Deuses de Arton; Poderes de Destino > Herois de Arton |
| doencas |  | Perigos > Ameaças de Arton; Perigos > Tormenta20 - Jogo do Ano |
| dragao jovem |  | Ameaças > Tormenta20 - Jogo do Ano; Montarias > Ameaças de Arton |
| dragonete |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| dromedario |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| druida |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| duro como aco |  | Poderes (Guerreiro) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| elefante |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| elemental do veneno |  | Ameaças > Duelo de Dragões; Parceiros > Ameaças de Arton |
| emboscar |  | Poderes (Caçador) > Tormenta20 - Jogo do Ano; Poderes (Ladino) > tormenta20 - jogo do ano |
| escudeiro |  | Ameaças > Ameaças de Arton; Origens > A Lenda de Ghanor; Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano |
| escuridao |  | Magias > Tormenta20 - Jogo do Ano; Perigos > Tormenta20 - Jogo do Ano |
| esgrima elfica |  | Poderes (Bardo) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| esgrimista |  | Poderes (Bucaneiro) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| especializacao em armadura |  | Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| estandarte |  | Ferramentas > Herois de Arton; Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano |
| estilo classico |  | Poderes (Guerreiro) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| estrategista |  | Papéis no Grupo > Compendio T20; Poderes (Nobre) > Tormenta20 - Jogo do Ano |
| exaltacao do rejeitado |  | Poderes (Clérigo) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| executor |  | Ameaças > Uma Visita a Vectora; Poderes (Guerreiro) > Herois de Arton |
| forjador liturgico |  | Ameaças > Ameaças de Arton; Distinções > Deuses de Arton |
| formidavel |  | Dificuldades de Teste > Compendio T20; Encantamentos de Itens Mágicos > Tormenta20 - Jogo do Ano |
| frade |  | Categorias de Poder > Deuses de Arton; Classes > Deuses de Arton |
| galhada femea |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| galhada macho |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| gargula |  | Ameaças > Ameaças de Arton; Ameaças > Tormenta20 - Jogo do Ano; Encantamentos de Itens Mágicos > Herois de Arton |
| gatuno |  | Ameaças > Ameaças de Arton; Poderes (Ladino) > tormenta20 - jogo do ano |
| ginete de javali |  | Poderes (Cavaleiro) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| gorlogg |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| gorlogg alfa |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| grifo |  | Ameaças > Tormenta20 - Jogo do Ano; Montarias > Tormenta20 - Jogo do Ano |
| guarda |  | Melhorias de Item > Herois de Arton; Origens > Tormenta20 - Jogo do Ano |
| guardiao |  | Encantamentos de Armaduras > Tormenta20 - Jogo do Ano; Parceiros > Tormenta20 - Jogo do Ano |
| guerreiro |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| heranca erudita |  | Poderes (Arcanista) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| hiena |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton |
| hienodonte |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| hippossauro |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| homunculo |  | Ameaças > Ameaças de Arton; Poderes (Inventor) > Tormenta20 - Jogo do Ano |
| impeto |  | Poderes (Bárbaro) > Tormenta20 - Jogo do Ano; Poderes (Caçador) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| inercia do aco |  | Poderes (Cavaleiro) > Herois de Arton; Poderes (Guerreiro) > Herois de Arton |
| inventor |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| ladino |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| leao |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| lendas e historias |  | Magias > Tormenta20 - Jogo do Ano; Poderes (Bardo) > Tormenta20 - Jogo do Ano |
| lobo do mar |  | Ameaças > Ameaças de Arton; Poderes (Bucaneiro) > Herois de Arton |
| lobo-das-cavernas |  | Ameaças > Tormenta20 - Jogo do Ano; Montarias > Tormenta20 - Jogo do Ano |
| luminar |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| lutador |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| magia performatica |  | Poderes (Arcanista) > Herois de Arton; Poderes (Bardo) > Herois de Arton |
| mamute |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| mao amiga |  | Poderes (Bucaneiro) > A Lenda de Ghanor; Poderes de Grupo > Herois de Arton |
| mensageiro |  | Origens > Herois de Arton; Serviços > Tormenta20 - Jogo do Ano |
| mistico |  | Categorias de Poder > Dragão Brasil; Classes > Dragão Brasil - 199 |
| nobre |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| ogro |  | Ameaças > Ameaças de Arton; Raças > Ameaças de Arton |
| oleo |  | Alimentos > Tormenta20; Equipamentos > Tormenta20 - Jogo do Ano |
| paladino |  | Categorias de Poder > tormenta20 - jogo do ano; Classes > tormenta20 - jogo do ano |
| pegaso |  | Ameaças > Deuses de Arton; Montarias > Deuses de Arton |
| pegaso de khalmyr |  | Ameaças > Deuses de Arton; Montarias > Deuses de Arton |
| pilly |  | Ameaças > Deuses de Arton; Parceiros > Deuses de Arton |
| pirata oceanico |  | Poderes (Bucaneiro) > Dragão Brasil - 212; Poderes de Raça > Herois de Arton |
| pistoleiro |  | Ameaças > Ameaças de Arton; Poderes (Bucaneiro) > Tormenta20 - Jogo do Ano |
| platan |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| poderoso |  | Condições > Dragão Brasil - 219; Melhorias de Item > Tormenta20 - Jogo do Ano |
| presenca majestosa |  | Poderes (Nobre) > Tormenta20 - Jogo do Ano; Poderes (Vampiro) > Dragão Brasil |
| protetor |  | Ameaças > Deuses de Arton; Encantamentos de Armaduras > Tormenta20 - Jogo do Ano; Poderes (Paladino) > Dragão Brasil - 212 |
| refugio |  | Aventuras > Compendio T20; Magias > Tormenta20 - Jogo do Ano |
| rinoceronte |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| rinoceronte lanoso |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| samurai |  | Categorias de Poder > Dragão Brasil; Classes > Dragão Brasil - 199 |
| sapo atroz |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| selako |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| solidez |  | Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano; Poderes (Guerreiro) > Tormenta20 - Jogo do Ano |
| sombra |  | Poderes (Ladino) > tormenta20 - jogo do ano; Serviços > Herois de Arton |
| sono |  | Magias > Tormenta20 - Jogo do Ano; Perigos > Tormenta20 - Jogo do Ano |
| tatu-montanha |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| tigre |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| tirano do terceiro |  | Ameaças > Tormenta20 - Jogo do Ano; Distinções > Deuses de Arton |
| titulo |  | Poderes (Cavaleiro) > Tormenta20 - Jogo do Ano; Poderes (Nobre) > Tormenta20 - Jogo do Ano |
| tomo de guerra |  | Esotéricos > Ameaças de Arton; Esotéricos > Duelo de Dragões |
| treinador |  | Categorias de Poder > Herois de Arton; Classes > Herois de Arton |
| trobo |  | Ameaças > Ameaças de Arton; Animais > Tormenta20 - Jogo do Ano; Montarias > Ameaças de Arton |
| trog |  | Ameaças > Tormenta20 - Jogo do Ano; Raças > Tormenta20 - jogo do ano |
| troll |  | Ameaças > Tormenta20 - Jogo do Ano; Montarias > Ameaças de Arton |
| trombeta do cruzado |  | Ferramentas > Deuses de Arton; Instrumentos Musicais > Deuses de Arton |
| tumarkhan |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| tuntram |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| unicornio |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| urso das cavernas |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| urso das neves |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| urso panda |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
| urso pardo |  | Ameaças > Ameaças de Arton; Animais > Ameaças de Arton; Montarias > Ameaças de Arton |
| valentao |  | Poderes (Guerreiro) > Tormenta20 - Jogo do Ano; Poderes (Lutador) > Tormenta20 - Jogo do Ano |
| vampiro |  | Ameaças > Tormenta20 - Jogo do Ano; Categorias de Poder > Dragão Brasil; Raças > Dragão Brasil - 220 |
| veloz |  | Condições > Dragão Brasil - 219; Encantamentos de Itens Mágicos > Tormenta20 - Jogo do Ano |
| vigilante |  | Ameaças > Uma Visita a Vectora; Melhorias de Item > Tormenta20 - Jogo do Ano; Parceiros > Tormenta20 - Jogo do Ano |
| warg |  | Ameaças > Ameaças de Arton; Montarias > Ameaças de Arton |
