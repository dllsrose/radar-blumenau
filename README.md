# Radar Blumenau

Observatório cidadão independente: propostas, presença e votos, com fontes oficiais e sem ranking.

Site: https://dllsrose.github.io/radar-blumenau/

## Atualização

A coleta identificada roda no computador do responsável, pelo Agendador de Tarefas do Windows, diariamente às 03h17 de Brasília. É necessário manter o computador ligado, conectado e com a sessão do usuário iniciada (pode estar bloqueada). O Git usa a autorização existente no Gerenciador de Credenciais; nenhuma senha ou chave fica neste repositório.

O programa consulta o portal público, valida a base contra a versão anterior e envia somente dist/data.json. O GitHub Actions executa os testes e publica no Pages. Se a coleta encontrar verificação humana, falha de rede ou perda de dados, a publicação anterior é preservada. O histórico do GitHub mostra publicações; falhas locais ficam no log do computador.

O início do histórico publicado é preservado. As execuções revisitam os últimos 45 dias e aos domingos todo o período coletado. O histórico anterior a novembro de 2026 ainda será ampliado separadamente.

## Fontes e limites

Fontes: https://digital.camarablu.sc.gov.br/ e https://camarablu.sc.gov.br/quem-sao/
Cada registro possui link para a fonte. Cadastro inclui titulares e substitutos da legislatura; não implica ocupação simultânea das cadeiras. Ausência de registro não vira falta. Auditoria por amostragem em dist/audit.json, sem afirmar validação integral do mandato.

As categorias e recorrências são heurísticas transparentes. Repetição não prova falta de atendimento. Textos são alegações dos autores. Contatos privados reconhecidos por padrão são ocultados da cópia textual.

## Executar manualmente

Python 3.12: instalar requirements.txt, executar `python -m unittest -v test_radar.py`, `python radar.py --start 2026-11-01 --baseline dist/data.json` e `python verify_site.py`.
Para prévia, executar `node serve.cjs` e abrir http://127.0.0.1:4173.

Os arquivos dist e os fontes estão diretamente versionados. radar-source.zip é apenas o pacote inicial de arquivo, não é mais usado no deploy. Não publicar .cache, .local, logs, credenciais ou arquivos de ambiente.

Correções: https://github.com/dllsrose/radar-blumenau/issues/new
