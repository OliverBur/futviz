// "Ver tabla": los mismos puntos que se ven en la gráfica (filtros incluidos), en un DataGrid dentro
// de un panel lateral. Sirve a dos cosas:
//   - es la vista accesible del gráfico (todo valor que muestra un tooltip está aquí, sin
//     depender del mouse), y
//   - deja ordenar por cualquier columna, buscar por nombre y bajar el CSV de lo que se ve.
// Las columnas las arma la vista (`columnas`: depende de qué ejes tiene); la fila `id` es la fila de
// la tabla de datos. La casilla de la primera columna fija o quita al jugador en la gráfica, igual
// que el Top 5 y el buscador.
import { useMemo } from "react";
import Box from "@mui/material/Box";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import Close from "@mui/icons-material/Close";
import { DataGrid } from "@mui/x-data-grid";
import { esES } from "@mui/x-data-grid/locales";

const textoGrid = esES.components.MuiDataGrid.defaultProps.localeText;

export function Tabla({ abierta, onCerrar, filas, columnas, ordenInicial, fijadas, onAlternar, onFijar, titulo,
  entidad, archivo }) {
  // Las filas fijadas son las SELECCIONADAS: la casilla de la primera columna fija o quita al
  // jugador. (El DataGrid gratuito solo permite varias filas seleccionadas con casillas; sin
  // ellas, un `rowSelectionModel` con más de un id lanza el error #84.) El estado vive en la
  // gráfica y la tabla solo lo refleja; un clic en cualquier otra celda también alterna.
  const seleccion = useMemo(() => ({ type: "include", ids: new Set(fijadas) }), [fijadas]);

  return (
    <Drawer anchor="right" open={abierta} onClose={onCerrar}
      slotProps={{ paper: { sx: { width: "min(940px, 100vw)", display: "flex", flexDirection: "column", p: 2, gap: 1.5 } } }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 1 }}>
        <Box>
          <Typography component="h2" sx={{ fontSize: 17, fontWeight: 700, color: "primary.main" }}>Tabla de {entidad}</Typography>
          <Typography sx={{ fontSize: 13, color: "text.secondary" }}>
            {titulo} · {filas.length.toLocaleString("es-MX")} {entidad} · clic en una fila para fijarla en la gráfica
          </Typography>
        </Box>
        <IconButton aria-label="Cerrar la tabla" onClick={onCerrar} edge="end"><Close /></IconButton>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <DataGrid
          rows={filas} columns={columnas} density="compact" showToolbar
          localeText={textoGrid}
          initialState={{
            sorting: { sortModel: [ordenInicial] },
            pagination: { paginationModel: { pageSize: 50 } },
          }}
          pageSizeOptions={[25, 50, 100]}
          checkboxSelection disableRowSelectionOnClick
          rowSelectionModel={seleccion}
          onRowSelectionModelChange={(m) => onFijar(m.ids)}
          // La casilla ya cambia la selección por su cuenta; solo las demás celdas alternan aquí.
          onCellClick={(p) => { if (p.field !== "__check__") onAlternar(p.id); }}
          slotProps={{ toolbar: { csvOptions: { fileName: archivo, utf8WithBom: true } } }}
          sx={{
            border: 1, borderColor: "divider", "& .MuiDataGrid-row": { cursor: "pointer" },
            // "Seleccionar todo" fijaría a cientos de jugadores: no tiene sentido aquí.
            "& .MuiDataGrid-columnHeaderCheckbox .MuiCheckbox-root": { display: "none" },
          }}
        />
      </Box>
    </Drawer>
  );
}
