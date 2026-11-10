-- CCM520 - Internet das Coisas | Projeto 2 (o mesmo script da Aula 9)
-- Executado pelo MySQL apenas na PRIMEIRA inicialização (volume vazio).
--
-- Usuários do banco (princípio do menor privilégio):
--   root    / fei2026     -> administração (só para você, no terminal)
--   cygnus  / cygnus2026  -> ESCREVE o histórico no banco "fei" (criado pelo docker-compose)
--   grafana / grafana2026 -> só LÊ o banco "fei" (fonte de dados do Grafana)

CREATE USER IF NOT EXISTS 'grafana'@'%' IDENTIFIED BY 'grafana2026';
GRANT SELECT ON `fei`.* TO 'grafana'@'%';
FLUSH PRIVILEGES;
