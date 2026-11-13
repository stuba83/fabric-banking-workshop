/* ============================================================================
   FAC_WH_Gold  -  01_esquemas_tablas.sql
   Demo A (se ejecuta sobre el Warehouse FAC_WH_Gold)

   Qué crea (todo idempotente: se puede ejecutar varias veces sin error ni pérdida):
     - Esquemas por dominio: clientes, cuentas, transacciones y operacion.
     - Tablas de destino "oro" del Warehouse (modelo estrella) y tablas de control.
     - Llaves PRIMARY KEY / FOREIGN KEY sin validación (NOT ENFORCED): sirven como
       metadatos para Power BI y el optimizador; el motor NO impide duplicados.

   Reglas de la superficie T-SQL de Fabric que se respetan aquí (ver README):
     - Solo tipos soportados: varchar (no nvarchar), datetime2(6) (no datetime),
       decimal(18,2) (no money), bigint/int (no tinyint).
     - Las llaves se agregan con ALTER TABLE; no se pueden declarar dentro de CREATE TABLE.
     - Sin DEFAULT, CHECK, IDENTITY, columnas calculadas ni triggers.
     - La intercalación por defecto distingue mayúsculas (Latin1_General_100_BIN2_UTF8):
       por eso todos los nombres van en minúsculas y se escriben igual en todo el código.

   Se ejecuta conectado a la base FAC_WH_Gold. Las tablas del Lakehouse se leen en
   02_procedimientos.sql con nombre de tres partes: AB_Lakehouse.dbo.<tabla>.
   ============================================================================ */

-- 1. Esquemas por dominio ----------------------------------------------------
-- CREATE SCHEMA debe ser la única instrucción del lote: por eso va dentro de sp_executesql.
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'clientes')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA clientes';
END;

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'cuentas')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA cuentas';
END;

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'transacciones')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA transacciones';
END;

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'operacion')
BEGIN
    EXEC sp_executesql N'CREATE SCHEMA operacion';
END;
GO

-- 2. Dominio clientes ----------------------------------------------------------
IF OBJECT_ID(N'clientes.dim_sucursal', N'U') IS NULL
BEGIN
    CREATE TABLE clientes.dim_sucursal (
        sucursal_id      varchar(20)   NOT NULL,
        nombre_sintetico varchar(100)  NOT NULL,
        provincia        varchar(30)   NOT NULL,
        fecha_carga      datetime2(6)  NOT NULL,
        lote_id          varchar(36)   NOT NULL
    );
    ALTER TABLE clientes.dim_sucursal
        ADD CONSTRAINT pk_dim_sucursal PRIMARY KEY NONCLUSTERED (sucursal_id) NOT ENFORCED;
END;
GO

IF OBJECT_ID(N'clientes.dim_cliente', N'U') IS NULL
BEGIN
    CREATE TABLE clientes.dim_cliente (
        cliente_id       varchar(20)   NOT NULL,
        nombre_sintetico varchar(100)  NOT NULL,
        fecha_alta       date          NOT NULL,
        segmento         varchar(20)   NOT NULL,
        grupo_edad       varchar(10)   NOT NULL,
        provincia        varchar(30)   NOT NULL,
        sucursal_id      varchar(20)   NOT NULL,
        fecha_carga      datetime2(6)  NOT NULL,
        lote_id          varchar(36)   NOT NULL
    );
    ALTER TABLE clientes.dim_cliente
        ADD CONSTRAINT pk_dim_cliente PRIMARY KEY NONCLUSTERED (cliente_id) NOT ENFORCED;
    ALTER TABLE clientes.dim_cliente
        ADD CONSTRAINT fk_dim_cliente_sucursal FOREIGN KEY (sucursal_id)
        REFERENCES clientes.dim_sucursal (sucursal_id) NOT ENFORCED;
END;
GO

-- 3. Dominio cuentas -----------------------------------------------------------
IF OBJECT_ID(N'cuentas.dim_producto', N'U') IS NULL
BEGIN
    CREATE TABLE cuentas.dim_producto (
        producto_id      varchar(20)   NOT NULL,
        nombre_sintetico varchar(100)  NOT NULL,
        familia          varchar(30)   NOT NULL,
        moneda           varchar(3)    NOT NULL,
        fecha_carga      datetime2(6)  NOT NULL,
        lote_id          varchar(36)   NOT NULL
    );
    ALTER TABLE cuentas.dim_producto
        ADD CONSTRAINT pk_dim_producto PRIMARY KEY NONCLUSTERED (producto_id) NOT ENFORCED;
END;
GO

IF OBJECT_ID(N'cuentas.dim_cuenta', N'U') IS NULL
BEGIN
    CREATE TABLE cuentas.dim_cuenta (
        cuenta_id        varchar(20)    NOT NULL,
        cliente_id       varchar(20)    NOT NULL,
        producto_id      varchar(20)    NOT NULL,
        fecha_apertura   date           NOT NULL,
        moneda           varchar(3)     NOT NULL,
        saldo_inicial    decimal(18,2)  NOT NULL,
        fecha_carga      datetime2(6)   NOT NULL,
        lote_id          varchar(36)    NOT NULL
    );
    ALTER TABLE cuentas.dim_cuenta
        ADD CONSTRAINT pk_dim_cuenta PRIMARY KEY NONCLUSTERED (cuenta_id) NOT ENFORCED;
    ALTER TABLE cuentas.dim_cuenta
        ADD CONSTRAINT fk_dim_cuenta_cliente FOREIGN KEY (cliente_id)
        REFERENCES clientes.dim_cliente (cliente_id) NOT ENFORCED;
    ALTER TABLE cuentas.dim_cuenta
        ADD CONSTRAINT fk_dim_cuenta_producto FOREIGN KEY (producto_id)
        REFERENCES cuentas.dim_producto (producto_id) NOT ENFORCED;
END;
GO

-- 4. Dominio transacciones -----------------------------------------------------
IF OBJECT_ID(N'transacciones.fact_transaccion', N'U') IS NULL
BEGIN
    CREATE TABLE transacciones.fact_transaccion (
        transaccion_id   varchar(20)    NOT NULL,
        cuenta_id        varchar(20)    NOT NULL,
        fecha_hora       datetime2(6)   NOT NULL,   -- hora local de Costa Rica guardada tal cual (sin zona)
        fecha            date           NOT NULL,
        tipo_transaccion varchar(30)    NOT NULL,
        direccion        varchar(10)    NOT NULL,   -- CREDITO = entrada de dinero; DEBITO = salida
        canal            varchar(20)    NOT NULL,
        monto            decimal(18,2)  NOT NULL,   -- magnitud positiva; la direccion define el efecto
        moneda           varchar(3)     NOT NULL,
        estado           varchar(15)    NOT NULL,
        fecha_carga      datetime2(6)   NOT NULL,
        lote_id          varchar(36)    NOT NULL
    );
    ALTER TABLE transacciones.fact_transaccion
        ADD CONSTRAINT pk_fact_transaccion PRIMARY KEY NONCLUSTERED (transaccion_id) NOT ENFORCED;
    ALTER TABLE transacciones.fact_transaccion
        ADD CONSTRAINT fk_fact_transaccion_cuenta FOREIGN KEY (cuenta_id)
        REFERENCES cuentas.dim_cuenta (cuenta_id) NOT ENFORCED;
END;
GO

IF OBJECT_ID(N'transacciones.resumen_mes_canal', N'U') IS NULL
BEGIN
    CREATE TABLE transacciones.resumen_mes_canal (
        mes              varchar(7)     NOT NULL,   -- yyyy-MM
        canal            varchar(20)    NOT NULL,
        transacciones    bigint         NOT NULL,
        monto_creditos   decimal(18,2)  NOT NULL,
        monto_debitos    decimal(18,2)  NOT NULL,
        fecha_carga      datetime2(6)   NOT NULL,
        lote_id          varchar(36)    NOT NULL
    );
    ALTER TABLE transacciones.resumen_mes_canal
        ADD CONSTRAINT pk_resumen_mes_canal PRIMARY KEY NONCLUSTERED (mes, canal) NOT ENFORCED;
END;
GO

-- 5. Dominio operacion: bitácora y reconciliación ------------------------------
-- Cada INSERT ... VALUES crea un archivo Parquet pequeño; para una bitácora con pocas
-- filas por corrida es aceptable. A mayor volumen conviene registrar fuera del Warehouse.
IF OBJECT_ID(N'operacion.bitacora_carga', N'U') IS NULL
BEGIN
    CREATE TABLE operacion.bitacora_carga (
        lote_id        varchar(36)   NOT NULL,
        procedimiento  varchar(128)  NOT NULL,
        estado         varchar(10)   NOT NULL,   -- INICIO | OK | ERROR
        filas_tabla_1  bigint        NULL,
        filas_tabla_2  bigint        NULL,
        mensaje        varchar(4000) NULL,
        usuario        varchar(128)  NULL,
        fecha_utc      datetime2(6)  NOT NULL
    );
END;
GO

IF OBJECT_ID(N'operacion.reconciliacion', N'U') IS NULL
BEGIN
    CREATE TABLE operacion.reconciliacion (
        lote_id    varchar(36)    NOT NULL,
        orden      int            NOT NULL,
        control    varchar(100)   NOT NULL,
        esperado   decimal(38,2)  NULL,
        observado  decimal(38,2)  NULL,
        estado     varchar(10)    NOT NULL,      -- OK | DIFIERE
        fecha_utc  datetime2(6)   NOT NULL
    );
END;
GO

/* ----------------------------------------------------------------------------
   REINICIO OPCIONAL (déjelo comentado). DROP TABLE destruye también el historial de
   time travel de la tabla; para vaciar conservando la tabla use TRUNCATE TABLE.
   Orden inverso a las dependencias:

   DROP TABLE IF EXISTS operacion.reconciliacion;
   DROP TABLE IF EXISTS operacion.bitacora_carga;
   DROP TABLE IF EXISTS transacciones.resumen_mes_canal;
   DROP TABLE IF EXISTS transacciones.fact_transaccion;
   DROP TABLE IF EXISTS cuentas.dim_cuenta;
   DROP TABLE IF EXISTS cuentas.dim_producto;
   DROP TABLE IF EXISTS clientes.dim_cliente;
   DROP TABLE IF EXISTS clientes.dim_sucursal;
   ---------------------------------------------------------------------------- */
