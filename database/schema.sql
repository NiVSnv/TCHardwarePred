-- ============================================================
-- TCHardwarePred - Schema do banco de dados (MySQL 8+)
-- ============================================================

CREATE DATABASE IF NOT EXISTS tchardwarepred
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE tchardwarepred;

-- ------------------------------------------------------------
-- Tabela 1: pontuações de hardware (3DMark Time Spy)
-- Guarda, individualmente, a pontuação de cada CPU e cada GPU.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hardware_scores (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tipo            ENUM('CPU', 'GPU') NOT NULL,
    fabricante      VARCHAR(50)  NOT NULL,
    modelo          VARCHAR(100) NOT NULL,
    pontuacao_3dmark INT NOT NULL,          -- CPU Score ou Graphics Score (Time Spy)
    fonte           VARCHAR(50) DEFAULT 'manual',  -- manual | 3dmark_export | 3dmark_api
    atualizado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tipo_modelo (tipo, modelo)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Tabela 2: combinações CPU + GPU e o FPS observado num jogo
-- É a base rotulada (dataset supervisionado) usada pelo scikit-learn.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fps_benchmarks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    cpu_id      INT NOT NULL,
    gpu_id      INT NOT NULL,
    jogo        VARCHAR(100) NOT NULL,      -- ex: 'Counter-Strike 2' (por enquanto só CS)
    resolucao   VARCHAR(20)  DEFAULT '1080p',
    fps_medio   FLOAT NOT NULL,
    criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fps_cpu FOREIGN KEY (cpu_id) REFERENCES hardware_scores(id),
    CONSTRAINT fk_fps_gpu FOREIGN KEY (gpu_id) REFERENCES hardware_scores(id),
    INDEX idx_jogo (jogo)
) ENGINE=InnoDB;
