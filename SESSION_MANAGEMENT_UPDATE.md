# Sistema de Gestión de Sesiones - AIPost

## Resumen de Cambios

Se ha implementado un nuevo sistema de gestión de sesiones que separa claramente la autenticación de AIPost de la conexión con LinkedIn.

## Nuevas Variables de Estado

### Variables de AIPost
- `aipost_logged_in`: Indica si el usuario ha iniciado sesión en AIPost
- `aipost_session_revalidated`: Flag para evitar re-validaciones innecesarias
- `user`: Información del usuario de AIPost

### Variables de LinkedIn (existentes)
- `li_connected`: Indica si LinkedIn está conectado
- `li_token_data`: Datos del token de LinkedIn
- `li_user_info`: Información del usuario de LinkedIn
- `user_accounts`: Cuentas de LinkedIn disponibles
- `selected_account`: Cuenta seleccionada actualmente

### Variables de LinkedIn (nueva claridad)
- `linkedin_logged_in`: Bandera que indica si existe una sesión local marcada de LinkedIn (separada de `li_connected`)

## Nuevas Funciones de Inicialización

### `initialize_aipost_session()`
Inicializa las variables específicas de AIPost:
- `aipost_logged_in`: False
- `aipost_session_revalidated`: False
- `user`: None

### `initialize_supabase_session()`
Inicializa las variables específicas de Supabase:
- `session_revalidated`: False
- `supabase_session_active`: False

## Funciones Actualizadas

### `revalidate_aipost_session()`
- Ahora usa `aipost_session_revalidated` en lugar de `session_revalidated`
- Establece `aipost_logged_in` (sin tocar flags de LinkedIn)

### `login()`
- Establece `aipost_logged_in = True` cuando el login es exitoso

### `logout()`
- Limpia `aipost_logged_in = False`
- Limpia todas las variables de LinkedIn relacionadas (no mezcla responsabilidades)

### `_validate_platform_session()`
- Ahora verifica `aipost_logged_in` en lugar de la antigua mezcla de flags

## Archivos Modificados

1. **src/supabase_auth.py**
   - Nuevas funciones de inicialización
   - Actualizada función de login/logout
   - Actualizada función de revalidación

2. **src/linkedin_auth.py**
   - Actualizada validación de sesión de plataforma
   - Actualizada inicialización de estado
   - Actualizada función de display de estado

3. **app.py**
   - Inicialización de nuevas variables
   - Actualizada condición de redirección

4. **pages/*.py**
    - Actualizadas todas las páginas protegidas para usar `is_aipost_logged_in()` (helper centralizado)

## Migración Gradual

El sistema mantiene compatibilidad temporal con `logged_in` para facilitar la transición. En futuras versiones se eliminará esta variable.

## Beneficios

1. **Separación Clara**: AIPost y LinkedIn tienen estados independientes
2. **Mejor Control**: Cada servicio puede gestionar su propio estado
3. **Debugging Mejorado**: Más fácil identificar problemas de sesión
4. **Escalabilidad**: Fácil añadir nuevos servicios de autenticación
5. **Mantenimiento**: Código más organizado y fácil de mantener

