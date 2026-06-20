SET FOREIGN_KEY_CHECKS = 0;
SET SESSION sql_mode = 'NO_AUTO_VALUE_ON_ZERO,ALLOW_INVALID_DATES';
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS evalia_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE evalia_db;

CREATE TABLE IF NOT EXISTS auth_permission (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    content_type_id INT          NOT NULL,
    codename        VARCHAR(100) NOT NULL,
    UNIQUE KEY auth_permission_content_type_id_codename (content_type_id, codename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS django_content_type (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    app_label VARCHAR(100) NOT NULL,
    model     VARCHAR(100) NOT NULL,
    UNIQUE KEY django_content_type_app_label_model (app_label, model)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios_usuario (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    password     VARCHAR(128) NOT NULL,
    last_login   DATETIME(6)  NULL,
    is_superuser TINYINT(1)   NOT NULL DEFAULT 0,
    username     VARCHAR(150) NOT NULL UNIQUE,
    first_name   VARCHAR(150) NOT NULL DEFAULT '',
    last_name    VARCHAR(150) NOT NULL DEFAULT '',
    email        VARCHAR(254) NOT NULL DEFAULT '',
    is_staff     TINYINT(1)   NOT NULL DEFAULT 0,
    is_active    TINYINT(1)   NOT NULL DEFAULT 1,
    date_joined  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    rol          VARCHAR(20)  NOT NULL DEFAULT 'instructor'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios_usuario_groups (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    group_id   INT NOT NULL,
    UNIQUE KEY ux_usuario_group (usuario_id, group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios_usuario_user_permissions (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id    INT NOT NULL,
    permission_id INT NOT NULL,
    UNIQUE KEY ux_usuario_permission (usuario_id, permission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_trimestre (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    numero       SMALLINT UNSIGNED NOT NULL,
    nombre       VARCHAR(120)      NOT NULL DEFAULT '',
    anio         INT UNSIGNED      NULL,
    fecha_inicio DATE              NULL,
    fecha_fin    DATE              NULL,
    activo       TINYINT(1)        NOT NULL DEFAULT 1,
    UNIQUE KEY ux_trimestre_numero_anio (numero, anio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_gaes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(120) NOT NULL,
    descripcion TEXT         NULL,
    ficha_id    INT          NULL,
    activo      TINYINT(1)   NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_fase (
    id     INT AUTO_INCREMENT PRIMARY KEY,
    numero SMALLINT UNSIGNED NOT NULL UNIQUE,
    nombre VARCHAR(120)      NOT NULL DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_ficha (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    numero        VARCHAR(30)  NOT NULL UNIQUE,
    programa      VARCHAR(200) NOT NULL DEFAULT '',
    jornada       VARCHAR(50)  NOT NULL DEFAULT 'mañana',
    gaes_id       INT          NULL,
    trimestre_id  INT          NULL,
    instructor_id INT          NULL,
    estado        VARCHAR(20)  NOT NULL DEFAULT 'activo',
    CONSTRAINT fk_ficha_gaes       FOREIGN KEY (gaes_id)      REFERENCES evaluacion_gaes(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_ficha_trimestre  FOREIGN KEY (trimestre_id) REFERENCES evaluacion_trimestre(id) ON DELETE SET NULL,
    CONSTRAINT fk_ficha_instructor FOREIGN KEY (instructor_id) REFERENCES usuarios_usuario(id)    ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE evaluacion_gaes
    DROP FOREIGN KEY IF EXISTS fk_gaes_ficha;

ALTER TABLE evaluacion_gaes
    ADD CONSTRAINT fk_gaes_ficha FOREIGN KEY (ficha_id)
        REFERENCES evaluacion_ficha(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS evaluacion_resultado_aprendizaje (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    codigo       VARCHAR(60)  NOT NULL UNIQUE,
    nombre       VARCHAR(200) NOT NULL,
    descripcion  TEXT         NULL,
    trimestre_id INT          NULL,
    CONSTRAINT fk_ra_trimestre FOREIGN KEY (trimestre_id)
        REFERENCES evaluacion_trimestre(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_competencia (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    codigo       VARCHAR(60)  NOT NULL UNIQUE,
    nombre       VARCHAR(200) NOT NULL,
    descripcion  TEXT         NULL,
    fase_id      INT          NOT NULL,
    gaes_id      INT          NULL,
    ficha_id     INT          NULL,
    trimestre_id INT          NULL,
    activo       TINYINT(1)   NOT NULL DEFAULT 1,
    CONSTRAINT fk_competencia_fase      FOREIGN KEY (fase_id)      REFERENCES evaluacion_fase(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_competencia_gaes      FOREIGN KEY (gaes_id)      REFERENCES evaluacion_gaes(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_competencia_ficha     FOREIGN KEY (ficha_id)     REFERENCES evaluacion_ficha(id)     ON DELETE SET NULL,
    CONSTRAINT fk_competencia_trimestre FOREIGN KEY (trimestre_id) REFERENCES evaluacion_trimestre(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_checklist (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    titulo      VARCHAR(100) NOT NULL,
    descripcion TEXT         NOT NULL,
    activo      TINYINT(1)   NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_checklistitem (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    competencia_id INT          NULL,
    checklist_id   INT          NULL,
    criterio       VARCHAR(200) NOT NULL,
    descripcion    TEXT         NOT NULL,
    puntaje_maximo INT          NOT NULL DEFAULT 10,
    orden          INT          NOT NULL DEFAULT 0,
    etapa          VARCHAR(50)  NOT NULL DEFAULT '',
    CONSTRAINT fk_cli_competencia FOREIGN KEY (competencia_id)
        REFERENCES evaluacion_competencia(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cli_checklist FOREIGN KEY (checklist_id)
        REFERENCES evaluacion_checklist(id) ON DELETE CASCADE,
    INDEX idx_cli_orden (competencia_id, orden)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_aprendiz (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id       INT          NULL UNIQUE,
    propietario_id   INT          NULL,
    documento        VARCHAR(20)  NOT NULL UNIQUE,
    nombres          VARCHAR(100) NOT NULL,
    apellidos        VARCHAR(100) NOT NULL,
    email            VARCHAR(254) NOT NULL,
    telefono         VARCHAR(20)  NOT NULL DEFAULT '',
    ficha_id         INT          NULL,
    gaes_id          INT          NULL,
    fase_id          INT          NULL,
    programa         VARCHAR(100) NOT NULL DEFAULT '',
    trimestre        VARCHAR(10)  NOT NULL DEFAULT '',
    fecha_nacimiento DATE         NULL,
    direccion        TEXT         NULL,
    bloqueado        TINYINT(1)   NOT NULL DEFAULT 0,
    created_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at       DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_aprendiz_usuario     FOREIGN KEY (usuario_id)     REFERENCES usuarios_usuario(id) ON DELETE CASCADE,
    CONSTRAINT fk_aprendiz_propietario FOREIGN KEY (propietario_id) REFERENCES usuarios_usuario(id) ON DELETE SET NULL,
    CONSTRAINT fk_aprendiz_ficha       FOREIGN KEY (ficha_id)       REFERENCES evaluacion_ficha(id) ON DELETE SET NULL,
    CONSTRAINT fk_aprendiz_gaes        FOREIGN KEY (gaes_id)        REFERENCES evaluacion_gaes(id)  ON DELETE RESTRICT,
    CONSTRAINT fk_aprendiz_fase        FOREIGN KEY (fase_id)        REFERENCES evaluacion_fase(id)  ON DELETE RESTRICT,
    INDEX idx_aprendiz_nombres (nombres)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_evaluacion (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    aprendiz_id        INT          NOT NULL,
    juror_id           INT          NOT NULL,
    checklist_id       INT          NOT NULL,
    fecha              DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    observaciones      TEXT         NULL,
    calificacion_total DECIMAL(5,2) NOT NULL DEFAULT 0,
    estado             VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
    CONSTRAINT fk_eval_aprendiz  FOREIGN KEY (aprendiz_id)  REFERENCES evaluacion_aprendiz(id)  ON DELETE CASCADE,
    CONSTRAINT fk_eval_juror     FOREIGN KEY (juror_id)     REFERENCES usuarios_usuario(id)     ON DELETE CASCADE,
    CONSTRAINT fk_eval_checklist FOREIGN KEY (checklist_id) REFERENCES evaluacion_checklist(id) ON DELETE CASCADE,
    INDEX idx_eval_aprendiz_estado (aprendiz_id, estado),
    INDEX idx_eval_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_evaluacionitem (
    id            INT  AUTO_INCREMENT PRIMARY KEY,
    evaluacion_id INT  NOT NULL,
    item_id       INT  NOT NULL,
    puntaje       INT  NOT NULL DEFAULT 0,
    observaciones TEXT NULL,
    UNIQUE KEY ux_eval_item (evaluacion_id, item_id),
    CONSTRAINT fk_evitem_evaluacion FOREIGN KEY (evaluacion_id)
        REFERENCES evaluacion_evaluacion(id) ON DELETE CASCADE,
    CONSTRAINT fk_evitem_item FOREIGN KEY (item_id)
        REFERENCES evaluacion_checklistitem(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_resultado (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    aprendiz_id             INT          NOT NULL,
    promedio                DECIMAL(5,2) NOT NULL DEFAULT 0,
    calificacion_final      VARCHAR(20)  NOT NULL DEFAULT 'No evaluado',
    fecha_cierre            DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    observaciones_generales TEXT         NULL,
    CONSTRAINT fk_resultado_aprendiz FOREIGN KEY (aprendiz_id)
        REFERENCES evaluacion_aprendiz(id) ON DELETE CASCADE,
    INDEX idx_resultado_fecha (fecha_cierre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_invitacion (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    instructor_id          INT          NOT NULL,
    instructor_invitado_id INT          NULL,
    ficha_id               INT          NULL,
    checklist_id           INT          NULL,
    estado                 VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
    fecha_envio            DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    fecha_respuesta        DATETIME(6)  NULL,
    fecha_evaluacion       DATE         NULL,
    hora_evaluacion        TIME         NULL,
    mensaje                TEXT         NULL,
    CONSTRAINT fk_inv_instructor          FOREIGN KEY (instructor_id)          REFERENCES usuarios_usuario(id)     ON DELETE CASCADE,
    CONSTRAINT fk_inv_instructor_invitado FOREIGN KEY (instructor_invitado_id) REFERENCES usuarios_usuario(id)     ON DELETE CASCADE,
    CONSTRAINT fk_inv_ficha               FOREIGN KEY (ficha_id)               REFERENCES evaluacion_ficha(id)     ON DELETE CASCADE,
    CONSTRAINT fk_inv_checklist           FOREIGN KEY (checklist_id)           REFERENCES evaluacion_checklist(id) ON DELETE SET NULL,
    INDEX idx_inv_estado (estado),
    INDEX idx_inv_fecha (fecha_envio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluacion_invitacion_instructores_jurados (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    invitacion_id INT NOT NULL,
    usuario_id    INT NOT NULL,
    UNIQUE KEY ux_inv_jurado (invitacion_id, usuario_id),
    CONSTRAINT fk_inv_jur_inv FOREIGN KEY (invitacion_id)
        REFERENCES evaluacion_invitacion(id) ON DELETE CASCADE,
    CONSTRAINT fk_inv_jur_usr FOREIGN KEY (usuario_id)
        REFERENCES usuarios_usuario(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notificaciones_notificacion (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    destinatario_id INT          NOT NULL,
    emisor_id       INT          NULL,
    tipo            VARCHAR(30)  NOT NULL DEFAULT 'sistema',
    titulo          VARCHAR(200) NOT NULL,
    mensaje         TEXT         NOT NULL,
    estado          VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
    url_relacionada VARCHAR(255) NOT NULL DEFAULT '',
    fecha_envio     DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    fecha_leida     DATETIME(6)  NULL,
    CONSTRAINT fk_notif_destinatario FOREIGN KEY (destinatario_id)
        REFERENCES usuarios_usuario(id) ON DELETE CASCADE,
    CONSTRAINT fk_notif_emisor FOREIGN KEY (emisor_id)
        REFERENCES usuarios_usuario(id) ON DELETE SET NULL,
    INDEX idx_notif_dest_estado (destinatario_id, estado),
    INDEX idx_notif_fecha (fecha_envio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auditoria_logauditoria (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    modulo      VARCHAR(30)  NOT NULL,
    accion      VARCHAR(30)  NOT NULL,
    descripcion TEXT         NULL,
    objeto_id   VARCHAR(30)  NOT NULL DEFAULT '',
    objeto_tipo VARCHAR(60)  NOT NULL DEFAULT '',
    ip_address  VARCHAR(39)  NULL,
    user_agent  TEXT         NULL,
    usuario_id  INT          NULL,
    created_at  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_log_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios_usuario(id) ON DELETE SET NULL,
    INDEX idx_log_modulo_fecha (modulo, created_at),
    INDEX idx_log_usuario_fecha (usuario_id, created_at),
    INDEX idx_log_accion_fecha (accion, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS auditoria_bitacoraevaluacion (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    evaluacion_id     INT          NOT NULL,
    version           INT UNSIGNED NOT NULL DEFAULT 1,
    estado_anterior   VARCHAR(30)  NOT NULL DEFAULT '',
    estado_nuevo      VARCHAR(30)  NOT NULL DEFAULT '',
    observaciones     TEXT         NULL,
    modificado_por_id INT          NULL,
    created_at        DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY ux_bitacora_eval_version (evaluacion_id, version),
    CONSTRAINT fk_bitacora_evaluacion     FOREIGN KEY (evaluacion_id)
        REFERENCES evaluacion_evaluacion(id) ON DELETE CASCADE,
    CONSTRAINT fk_bitacora_modificado_por FOREIGN KEY (modificado_por_id)
        REFERENCES usuarios_usuario(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS django_migrations (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    app     VARCHAR(255) NOT NULL,
    name    VARCHAR(255) NOT NULL,
    applied DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS django_session (
    session_key  VARCHAR(40) NOT NULL PRIMARY KEY,
    session_data LONGTEXT    NOT NULL,
    expire_date  DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_session_expire (expire_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS django_admin_log (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    action_time     DATETIME(6)       NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    object_id       LONGTEXT          NULL,
    object_repr     VARCHAR(200)      NOT NULL,
    action_flag     SMALLINT UNSIGNED NOT NULL,
    change_message  LONGTEXT          NOT NULL,
    content_type_id INT               NULL,
    user_id         INT               NOT NULL,
    CONSTRAINT fk_admin_log_user         FOREIGN KEY (user_id)         REFERENCES usuarios_usuario(id)   ON DELETE CASCADE,
    CONSTRAINT fk_admin_log_content_type FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO evaluacion_fase (numero, nombre) VALUES
    (1, 'Análisis'),
    (2, 'Diseño'),
    (3, 'Desarrollo'),
    (4, 'Implementación'),
    (5, 'Pruebas'),
    (6, 'Documentación'),
    (7, 'Sustentación')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);