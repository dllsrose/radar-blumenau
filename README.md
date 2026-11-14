# Radar Blumenau

Observatório cidadão independente do trabalho legislativo de Blumenau. Sem notas, ranking ou opinião. Fontes: Câmara Municipal e seu portal digital Legisoft.

## O que o site faz

- Lista todos os participantes publicados para a legislatura 2025–2028, incluindo substitutos.
- Permite consultar propostas, autoria, presenças e votos nominais, sempre com links oficiais.
- Separa melhorias nos bairros, perguntas e cobranças, homenagens, propostas de lei e outros com regras iguais para todos.
- Busca menções a bairro, rua e assunto; filtra período e vereador; exporta os resultados.
- Cruza nome da rua e assunto em datas diferentes, com contagem, datas, autores e links. Repetição não prova que a Prefeitura ignorou o pedido ou que a obra não foi feita.
- Publica uma auditoria por amostragem e oferece correção por Issues.

## Coleta e proteção da publicação

`radar.py` percorre as páginas de documentos e sessões oficiais, com no máximo duas conexões e intervalo global mínimo de 0,8 segundo entre inícios de requisições. O cliente se identifica. Bloqueio antirrobô não é contornado.

O GitHub Actions executa diariamente às **03h17 de Brasília** (06h17 UTC). O horário é sujeito a atrasos do GitHub. Também executa em publicação de código e manualmente. A configuração inicial busca desde 01/01/2025. A primeira coleta histórica pode levar horas.

A saída só substitui a base após percorrer e validar o período. Falhas de rede, paginação vazia ou repetida, voto ilegível, falta de campos obrigatórios, desaparecimento de documentos ou redução de registros nominais bloqueiam a publicação. O job de deploy depende do sucesso da coleta e dos testes; uma falha mantém a versão já publicada. O histórico de execuções é o indicador do estado do robô.

`dist/data.json` contém data de coleta e cobertura. Não confunda a data de publicação do código com a data de atualização dos registros. O cache é separado por data e não é publicado.

## Método e limites

Contamos propostas originais, não pareceres, anexos, atas ou respostas. Coautorias podem aparecer em vários perfis. Não somar totais individuais. Textos publicados são alegações de seus autores.

Classificação e extração de logradouro são heurísticas, não campos oficiais. Abreviações conhecidas de logradouro são normalizadas; os grupos podem reunir trechos diferentes. Sem geocodificação inferida nem afirmação de obra pendente. Telefones e e-mails não institucionais identificados por padrão e CPFs formatados são ocultados na cópia textual; os links levam ao documento original.

Presença é o estado publicado em cada sessão, sem presumir ausência de quem não consta ou que uma pessoa tinha obrigação de participar durante afastamento. Abertura da sessão não mede permanência integral. As listas institucional e digital divergiam na conferência inicial; o Radar reúne todos os participantes da legislatura do portal digital, sem afirmar que os 18 ocupam simultaneamente 15 cadeiras.

`dist/audit.json` documenta a comparação com atas oficiais de 05 e 10/11/2026, sem divergências na amostra, e a comparação pendente de 12/11. A auditoria não cobre todo o mandato nem todos os votos. Não publicar motivos pessoais de ausências.

## Rodar localmente

Python 3.12 e Node.js:

```sh
pip install -r requirements.txt
python -m unittest -v test_radar.py
python radar.py --start 2025-01-01
python verify_site.py
node serve.cjs
```

Abra http://127.0.0.1:4173. Para retomar uma coleta interrompida no mesmo dia, reutilize o cache. Uma coleta nova usa uma pasta de cache nova. Não copie arquivos `.cache`, credenciais ou arquivos de ambiente para a publicação.

## Correções e domínio

Use a [solicitação de correção](https://github.com/dllsrose/radar-blumenau/issues/new?template=correcao.yml) com o link oficial e a divergência. Não envie dados privados. Correções são tratadas por revisão da regra, do vínculo de nomes ou da fonte; não alterar um resultado nominal sem evidência.

O endereço gratuito do GitHub Pages dispensa compra de domínio. Um domínio próprio é opcional e não foi contratado. A configuração HTTPS do domínio padrão permanece ativa.
