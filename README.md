# Radar Blumenau

Observatório cidadão independente: propostas, presença e votos, com fontes oficiais e sem notas de desempenho.

Site: https://dllsrose.github.io/radar-blumenau/

## Atualização

A coleta identificada roda no computador do responsável, pelo Agendador de Tarefas do Windows, diariamente às 03h17 de Brasília. Ao entrar no Windows, verifica se há uma atualização pendente; horários perdidos são recuperados. Uma verificação por hora permite tentar novamente após falha de rede. Depois do sucesso no dia, as verificações não repetem a coleta. É necessário estar conectado e com a sessão do usuário iniciada (pode estar bloqueada). O Git usa a autorização existente no Gerenciador de Credenciais; nenhuma senha ou chave fica neste repositório.

O programa consulta o portal público, valida a base contra a versão anterior e envia dist/data.json e dist/attendance-audit.json juntos. O GitHub Actions executa os testes e publica no Pages. Se a coleta encontrar verificação humana, falha de rede ou perda de dados, a publicação anterior é preservada. O histórico do GitHub mostra publicações; falhas locais ficam no log do computador.

O início do histórico publicado é preservado. A data inicial solicitada é 01/01/2025; a cobertura efetivamente validada consta de dist/data.json e do próprio site. A carga histórica só é publicada após completar a coleta e a validação. As execuções seguintes revisitam os últimos 45 dias e, a cada dia, uma parte do histórico anterior (um ano de propostas em dia fixo e um sétimo das reuniões antigas), de modo que todo o período coletado é reconferido a cada semana. `radar.py --full` reconfere tudo de uma vez.

## Fontes e limites

Fontes: https://digital.camarablu.sc.gov.br/ e https://camarablu.sc.gov.br/quem-sao/
Cada registro possui link para a fonte. Cadastro inclui titulares e substitutos da legislatura; não implica ocupação simultânea das cadeiras. Ausência de registro não vira falta. Reuniões ordinárias e extraordinárias publicadas incluem plenário, comissões e frentes parlamentares; os resumos de presença distinguem esses tipos. Nome publicado sem situação é exibido como “Situação não informada”. Conferência inicial por amostragem preservada em dist/audit.json; o levantamento ampliado está em dist/attendance-audit.json, com cobertura e pendências explícitas.

As categorias e recorrências são heurísticas transparentes. Repetição não prova falta de atendimento. Textos são alegações dos autores. Contatos privados reconhecidos por padrão são ocultados da cópia textual.

## Executar manualmente

Python 3.12: instalar requirements.txt, executar `python -m unittest -v test_radar.py`, `python radar.py --start 2025-01-01 --baseline dist/data.json` e `python verify_site.py`.
Para prévia, executar `node serve.cjs` e abrir http://127.0.0.1:4173.

Os arquivos dist e os fontes estão diretamente versionados. Não publicar .cache, .local, logs, credenciais ou arquivos de ambiente.

Correções: https://github.com/dllsrose/radar-blumenau/issues/new

Resultados nominais explicitamente indisponíveis na Câmara, confirmados após seis consultas, permanecem sinalizados e vinculados à fonte, fora do total de votações publicadas. As revisões semanais os consultam novamente. Um resultado indisponível nunca substitui votos nominais já publicados.

## Conferência documental de presenças

`dist/attendance-audit.json` reúne o inventário completo de atas levantadas nos documentos legislativos de 2025 e 2026 e a comparação com páginas de reunião. A conferência integra a rotina diária local. O inventário de todos os anos desde 2025 e o calendário completo são percorridos a cada execução. PDFs novos e pendentes são tentados diariamente; os já obtidos são revisitados aos domingos ou após sete dias sem revisão integral. A interface exibe a data da conferência, a cobertura elegível e os casos pendentes.

A ordenação de ausências usa as atas, separa justificadas das não classificadas e não converte ausência de nome em falta. Licenças, afastamentos, contradições e reuniões com associação ambígua ficam fora do percentual. O denominador é presença + ausência explicitamente registradas; não representa dias de exercício legal nem todas as sessões obrigatórias. Plenário ordinário e extraordinário são comparados separadamente. Comissões e outros tipos aparecem no relatório, sem entrar na ordenação do plenário.

`attendance_collect.py` coleta e valida a evolução contra a versão anterior; `attendance_audit.py` contém as regras de leitura e cruzamento; `dist/attendance.js`, as regras de contagem e interface. Os testes cobrem afastamentos, nomes omitidos, contradições, composição de comissão, duplicidade e filtros de calendário sem distinção de maiúsculas. Os PDFs originais e seus textos completos ficam apenas no cache local, pois podem conter contatos e motivos pessoais; o relatório público publica estados, nomes, fontes e hashes, sem esses textos.

As revisões de associações e republicações estão em `attendance_reviews.json`, vinculadas ao SHA-256 do PDF. Arquivo alterado desativa a revisão específica. Reuniões de plenário no mesmo dia com números e horários de abertura distintos são contadas separadamente. PDFs são obtidos após renovar a página oficial do documento, usando o endereço do visualizador e o referenciador oficial.
# Revisões documentais das atas

`attendance_reviews.json` contém revisões individuais vinculadas ao SHA-256 do PDF. Uma mudança no documento invalida a revisão; a validação impede publicação com perda de uma lista nominal anteriormente disponível. Datas corrigidas por pauta ou notícia oficial preservam `sourceDate`, `dateEvidence` e `dateSourceUrl`. A interface mostra a data escrita e a adotada, com a fonte.

As associações excepcionais exigem mesma data e família de reunião, além de justificativa documental; isso permite conciliar páginas intituladas “ordinária RF” com atas de reuniões extraordinárias sem alterar o tipo adotado no ranking. Revisões de listas nominais não inferem ausências por omissão e distinguem convidados em funções externas ao Legislativo. Os mesmos critérios são aplicados por `attendance_collect.py` na atualização local diária.
