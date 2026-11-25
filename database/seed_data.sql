-- ============================================================
-- Dados de exemplo (seed) - substitua/complemente com dados reais
-- coletados do 3DMark e de medições de FPS em Counter-Strike 2.
-- ============================================================
USE tchardwarepred;

-- CPUs (pontuação = 3DMark Time Spy CPU Score)
INSERT INTO hardware_scores (tipo, fabricante, modelo, pontuacao_3dmark) VALUES
('CPU', 'Intel', 'Core i5-10400F', 7368),
('CPU', 'Intel', 'Core i3-8145U', 1815),
('CPU', 'Intel', 'Core i5-12400F', 11155),
('CPU', 'Intel', 'Core i7-12700K', 17521),
('CPU', 'Intel', 'Core i9-13900K',  25702),
('CPU', 'AMD',   'Ryzen 3 3200G',   3446),
('CPU', 'AMD',   'Ryzen 5 3600',   7545),
('CPU', 'AMD',   'Ryzen 5 5600X',  8877),
('CPU', 'AMD',   'Ryzen 7 5800X',  12131),
('CPU', 'AMD',   'Ryzen 7 7800X3D', 14409)
ON DUPLICATE KEY UPDATE pontuacao_3dmark = VALUES(pontuacao_3dmark);

-- GPUs (pontuação = 3DMark Time Spy Graphics Score)
INSERT INTO hardware_scores (tipo, fabricante, modelo, pontuacao_3dmark) VALUES
('GPU', 'NVIDIA', 'GTX 1660 Super', 6870),
('GPU', 'NVIDIA', 'RTX 3060',       10183),
('GPU', 'NVIDIA', 'RTX 3070',      15976),
('GPU', 'NVIDIA', 'RTX 4070',      25293),
('GPU', 'NVIDIA', 'RTX 4080',      31574),
('GPU', 'NVIDIA', 'RTX 5060',    16202),
('GPU', 'AMD',    'RX 6600 XT',        10980),
('GPU', 'AMD',    'RX 5700 XT',        11110),
('GPU', 'AMD',    'RX 6700 XT',    14426),
('GPU', 'AMD',    'RX 7800 XT',    22973)
ON DUPLICATE KEY UPDATE pontuacao_3dmark = VALUES(pontuacao_3dmark);

-- Combinações CPU+GPU e FPS medido em Counter-Strike 2 (1080p, alto)
-- Valores ilustrativos para popular o modelo - troque pelos dados reais coletados.
INSERT INTO fps_benchmarks (cpu_id, gpu_id, jogo, resolucao, fps_medio)
SELECT c.id, g.id, 'Counter-Strike 2', '1080p', v.fps FROM (
    SELECT 'Core i5-10400F' cpu, 'GTX 1660 Super' gpu, 188 fps UNION ALL
    SELECT 'Core i3-8145U', 'RTX 5060',       220 UNION ALL
    SELECT 'Core i3-8145U', 'RX 7800 XT',       220 UNION ALL
    SELECT 'Core i5-10400F', 'RTX 3060',       310 UNION ALL
    SELECT 'Core i5-12400F', 'RX 6700 XT',       322 UNION ALL
    SELECT 'Core i5-12400F', 'RTX 3060',       279 UNION ALL
    SELECT 'Core i7-12700K', 'RTX 3070',       350 UNION ALL
    SELECT 'Core i7-12700K', 'RX 6700 XT',       322 UNION ALL
    SELECT 'Core i9-13900K', 'RTX 4080',       533 UNION ALL
    SELECT 'Core i9-13900K', 'RTX 4070',       443 UNION ALL
    SELECT 'Ryzen 3 3200G', 'RTX 4080',       237 UNION ALL
    SELECT 'Ryzen 5 3600',   'RX 6600',        134 UNION ALL
    SELECT 'Ryzen 3 3200G',  'RX 5700 XT',     235 UNION ALL
    SELECT 'Ryzen 5 5600X',  'RX 6700 XT',     254 UNION ALL
    SELECT 'Ryzen 5 5600X',  'RTX 4070',     443 UNION ALL
    SELECT 'Ryzen 7 5800X',  'RTX 3070',       441 UNION ALL
    SELECT 'Ryzen 7 5800X',  'RTX 3070',       441 UNION ALL
    SELECT 'Ryzen 7 7800X3D',  'RX 7800 XT',   426 UNION ALL
    SELECT 'Ryzen 7 5800X',  'GTX 1660 Super',       219 UNION ALL
    SELECT 'Ryzen 7 7800X3D','RTX 4080',       377
) v
JOIN hardware_scores c ON c.tipo = 'CPU' AND c.modelo = v.cpu
JOIN hardware_scores g ON g.tipo = 'GPU' AND g.modelo = v.gpu;
