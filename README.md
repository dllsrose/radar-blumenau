# Radar Blumenau

Observatório cidadão independente: propostas, presença e votos, com fontes oficiais e sem ranking.

Site: https://dllsrose.github.io/radar-blumenau/

## Atualização

A coleta identificada roda no computador do responsável, pelo Agendador de Tarefas do Windows, diariamente às 03h17 de Brasília. É necessário manter o computador ligado, conectado e com a sessão do usuário iniciada (pode estar bloqueada). O Git usa a autorização existente no Gerenciador de Credenciais; nenhuma senha ou chave fica neste repositório.

O programa consulta o portal público, valida a base contra a versão anterior e envia somente dist/data.json. O GitHub Actions executa os testes e publica no Pages. Se a coleta encontrar verificação humana, falha de rede ou perda de dados, a publicação anterior é preservada. O histórico do GitHub mostra publicações; falhas locais ficam no log do computador.

O início do histórico publicado é preservado. A data inicial solicitada é 01/01/2025; a cobertura efetivamente validada consta de dist/data.json e do próprio site. A carga histórica só é publicada após completar a coleta e a validação. As execuções seguintes revisitam os últimos 45 dias e aos domingos todo o período coletado.

## Fontes e limites

Fontes: https://digital.camarablu.sc.gov.br/ e https://camarablu.sc.gov.br/quem-sao/
Cada registro possui link para a fonte. Cadastro inclui titulares e substitutos da legislatura; não implica ocupação simultânea das cadeiras. Ausência de registro não vira falta. Reuniões ordinárias e extraordinárias publicadas incluem plenário, comissões e frentes parlamentares; os resumos de presença distinguem esses tipos. Nome publicado sem situação é exibido como “Situação não informada”. Auditoria por amostragem em dist/audit.json, sem afirmar validação integral do mandato.

As categorias e recorrências são heurísticas transparentes. Repetição não prova falta de atendimento. Textos são alegações dos autores. Contatos privados reconhecidos por padrão são ocultados da cópia textual.

## Executar manualmente

Python 3.12: instalar requirements.txt, executar `python -m unittest -v test_radar.py`, `python radar.py --start 2025-01-01 --baseline dist/data.json` e `python verify_site.py`.
Para prévia, executar `node serve.cjs` e abrir http://127.0.0.1:4173.

Os arquivos dist e os fontes estão diretamente versionados. radar-source.zip é apenas o pacote inicial de arquivo, não é mais usado no deploy. Não publicar .cache, .local, logs, credenciais ou arquivos de ambiente.

Correções: https://github.com/dllsrose/radar-blumenau/issues/new

Resultados nominais explicitamente indisponíveis na Câmara, confirmados após seis consultas, permanecem sinalizados e vinculados à fonte, fora do total de votações publicadas. As revisões semanais os consultam novamente. Um resultado indisponível nunca substitui votos nominais já publicados.
