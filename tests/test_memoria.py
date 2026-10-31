"""Pruebas de la memoria privada. Ejecutar:  python -m unittest discover -s tests -v"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import memoria as M  # noqa: E402


def pk(texto, history=None, chat="c1"):
    r = M.handle(texto, chat, history)
    return r["message"] if r else None


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.environ["PK_DATA_DIR"] = self.dir
        M._cache.update(mtime=None, datos=None)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)
        os.environ.pop("PK_DATA_DIR", None)
        M._cache.update(mtime=None, datos=None)


class Hechos(Base):
    def test_recuerda_que(self):
        self.assertIn("Listo, lo recordaré", pk("Recuerda que mi examen de cálculo es el viernes"))
        self.assertEqual([h["texto"] for h in M.hechos()], ["mi examen de cálculo es el viernes"])
        self.assertIn("ya lo tenía", pk("recuérdame que mi examen de cálculo es el viernes"))

    def test_explicito_no_secuestra_archivos(self):
        for f in ["guarda esto en un archivo llamado notas", "anota los continentes en el archivo mundo",
                  "recuerda", "guarda el archivo", "crea un bloc de notas llamado mundo"]:
            self.assertIsNone(pk(f), f)

    def test_auto_nombre_y_lugar(self):
        g = M.auto_guardar("Hola, me llamo ana lópez y vivo en Santa Ana")
        self.assertEqual([x["texto"] for x in g], ["Nombre: Ana López", "Vive en: Santa Ana"])
        self.assertIn("Guardé en tu memoria: Nombre: Ana López", M.nota_guardado(g))

    def test_auto_actualiza_misma_clave(self):
        M.auto_guardar("vivo en Santa Ana")
        g = M.auto_guardar("ahora vivo en San Salvador")
        self.assertEqual(g[0]["estado"], "actualizado")
        self.assertEqual([h["texto"] for h in M.hechos()], ["Vive en: San Salvador"])

    def test_auto_estudio_trabajo_gustos(self):
        g = M.auto_guardar("estudio economía y negocios en la ESEN")
        self.assertEqual(g[0]["texto"], "Estudia: economía y negocios en la ESEN")
        g = M.auto_guardar("mi comida favorita es la pupusa de queso, aunque a veces pizza")
        self.assertEqual(g[0]["texto"], "Favorito — comida: la pupusa de queso")
        g = M.auto_guardar("me gusta la guitarra eléctrica")
        self.assertEqual(g[0]["texto"], "Le gusta: la guitarra eléctrica")
        g = M.auto_guardar("mi perro se llama Max")
        self.assertEqual(g[0]["texto"], "Su perro: Max")

    def test_auto_no_guarda_ruido(self):
        for f in ["¿cómo me llamo?", "me llamo", "vivo en paz", "estudio para el examen mañana",
                  "trabajo en el proyecto de PK", "me gusta cómo respondes", "dime dónde vivo",
                  "me llamo muy rápido a las cosas importantes de mi vida y no sé si",
                  "me gusta que", "hola", "crea un archivo llamado mundo"]:
            self.assertEqual(M.auto_guardar(f), [], f)

    def test_parte_de_pregunta_se_ignora(self):
        g = M.auto_guardar("me llamo Ana, ¿y tú cómo te llamas?")
        self.assertEqual(g[0]["texto"], "Nombre: Ana")

    def test_no_guarda_secretos(self):
        self.assertIn("No guardo contraseñas", pk("recuerda que mi contraseña es 1234"))
        self.assertIn("No guardo contraseñas", pk("recuerda que mi tarjeta es 4111 1111 1111 1111"))
        self.assertIn("No guardo contraseñas", pk("recuerda que mi DUI es 01234567-8"))
        self.assertEqual(M.hechos(), [])

    def test_auto_desactivado(self):
        M.cambiar_config(hechos_auto=False)
        self.assertEqual(M.auto_guardar("me llamo Ana"), [])

    def test_limite(self):
        for i in range(M.MAX_HECHOS):
            M.agregar_hecho(f"dato número {i} distinto")
        _, estado = M.agregar_hecho("uno más que no cabe")
        self.assertEqual(estado, "lleno")


class Consultas(Base):
    def test_preguntas_directas(self):
        M.auto_guardar("me llamo Ana y vivo en Santa Ana")
        M.auto_guardar("mi color favorito es el azul")
        self.assertEqual(pk("¿Cómo me llamo?"), "Te llamas Ana.")
        self.assertEqual(pk("dónde vivo"), "Vives en Santa Ana.")
        self.assertEqual(pk("cuál es mi color favorito"), "Tu color favorito: el azul.")
        self.assertIn("Todavía no me has dicho dónde trabajas", pk("¿dónde trabajo?"))

    def test_que_sabes_de_mi(self):
        self.assertIn("Todavía no sé nada tuyo", pk("¿qué sabes de mí?"))
        M.auto_guardar("me llamo Ana")
        r = pk("qué recuerdas de mí")
        self.assertIn("• Nombre: Ana", r)
        self.assertIn("pestaña Memoria", r)

    def test_contexto_para_el_modelo(self):
        self.assertEqual(M.contexto("hola"), "")
        M.auto_guardar("me llamo Ana y vivo en Santa Ana")
        M.agregar_hecho("mi examen de cálculo es el viernes")
        c = M.contexto("cuándo es mi examen")
        self.assertTrue(c.splitlines()[1].startswith("- Nombre"))
        self.assertIn("examen de cálculo", c)
        self.assertLessEqual(len(M.contexto("x", max_chars=40)), 40 + 250)
        M.cambiar_config(usar=False)
        self.assertEqual(M.contexto("hola"), "")


class Historial(Base):
    def llenar(self):
        M.registrar("c1", "crea un bloc de notas con los continentes, llámalo mundo",
                    "Listo, creé el archivo mundo.txt con los 7 continentes.", "espacio")
        M.registrar("c2", "dame una biografía de Billie Joe Armstrong",
                    "Billie Joe Armstrong es el vocalista de Green Day...", "web")
        M.registrar("c2", "qué es el PIB", "El PIB es el valor de los bienes y servicios finales...", "documentos")

    def test_recuerda_entre_chats(self):
        self.llenar()
        r = pk("¿te acuerdas del archivo mundo que hicimos?", chat="c9")
        self.assertIn("mundo.txt", r)
        self.assertNotIn("Armstrong", r)
        r = pk("qué hicimos con Billie Joe", chat="c9")
        self.assertIn("Armstrong", r)

    def test_en_que_hemos_trabajado_da_lo_reciente(self):
        self.llenar()
        r = pk("¿en qué hemos trabajado?")
        self.assertIn("PIB", r)
        self.assertIn("mundo", r)

    def test_sin_resultados_no_inventa(self):
        self.llenar()
        self.assertIn("No encuentro nada así", pk("¿qué hicimos con el volcán Izalco?"))

    def test_recuerdas_flojo_no_secuestra(self):
        self.llenar()
        self.assertIsNone(pk("¿recuerdas la capital de Francia?"))

    def test_sin_historial_alguno(self):
        self.assertIn("Todavía no tengo recuerdos", pk("¿en qué hemos trabajado?"))

    def test_no_registra_trivial_ni_secreto_ni_herramientas(self):
        self.assertFalse(M.registrar("c", "hola", "hola", "charla"))
        self.assertFalse(M.registrar("c", "cuánto es 25 por 4 ahora mismo", "25 × 4 = 100", "herramienta"))
        self.assertFalse(M.registrar("c", "mi contraseña del wifi es patata", "ok la guardo", "charla"))
        self.assertFalse(M.registrar("c", "cuál es el pin de mi tarjeta que te dije", "no lo sé", "documentos"))
        self.assertEqual(M.episodios(), [])

    def test_no_repite_el_mismo(self):
        self.assertTrue(M.registrar("c", "qué es la inflación en economía", "Es el aumento...", "documentos"))
        self.assertFalse(M.registrar("c", "qué es la inflación en economía", "Es el aumento...", "documentos"))

    def test_limite_y_recorte(self):
        for i in range(M.MAX_EPISODIOS + 20):
            M.registrar("c", f"pregunta larga número {i} sobre economía", "respuesta " * 100, "documentos")
        eps = M.episodios()
        self.assertEqual(len(eps), M.MAX_EPISODIOS)
        self.assertLessEqual(len(eps[0]["respuesta"]), M.MAX_RESPUESTA)

    def test_historial_desactivado(self):
        M.cambiar_config(historial=False)
        self.assertFalse(M.registrar("c", "qué es la inflación en economía", "Es el aumento", "documentos"))


class Olvidar(Base):
    def setUp(self):
        super().setUp()
        M.auto_guardar("me llamo Ana y vivo en Santa Ana")
        M.agregar_hecho("mi examen de cálculo es el viernes")
        M.registrar("c1", "qué es la inflación en economía", "Es el aumento...", "documentos")

    def test_olvidar_algo(self):
        self.assertEqual(pk("olvida que vivo en Santa Ana"), "Olvidé: Vive en: Santa Ana.")
        self.assertNotIn("Santa Ana", json.dumps(M.hechos(), ensure_ascii=False))
        self.assertEqual(len(M.hechos()), 2)
        self.assertIn("No tengo guardado nada", pk("olvida lo de mi perro"))

    def test_olvidar_no_borra_de_mas(self):
        # «Ana» está en el nombre y en la ciudad: solo se borra lo que se pidió
        self.assertEqual(pk("olvida que me llamo Ana"), "Olvidé: Nombre: Ana.")
        self.assertEqual(sorted(h["texto"] for h in M.hechos()),
                         ["Vive en: Santa Ana", "mi examen de cálculo es el viernes"])

    def test_olvidar_con_empate_pregunta(self):
        M.agregar_hecho("mi examen de física es el lunes")
        r = pk("olvida mi examen")
        self.assertIn("coincide con varias", r)
        self.assertEqual(len(M.hechos()), 4)

    def test_olvidar_todo_pide_confirmacion(self):
        r = pk("olvida todo")
        self.assertTrue(r.startswith("¿Seguro?"))
        self.assertEqual(len(M.hechos()), 3)                          # todavía nada borrado
        hist = [{"role": "user", "content": "olvida todo"}, {"role": "assistant", "content": r}]
        self.assertIn("Cancelado", pk("no", hist))
        self.assertEqual(len(M.hechos()), 3)
        self.assertIn("olvidé todo: 3 datos tuyos y 1 recuerdo de conversaciones", pk("sí, olvídalo todo", hist))
        self.assertEqual((M.hechos(), M.episodios()), ([], []))

    def test_si_sin_pregunta_previa_no_borra(self):
        self.assertIsNone(pk("sí"))
        self.assertEqual(len(M.hechos()), 3)

    def test_olvidar_solo_historial(self):
        r = pk("olvida lo que hemos trabajado")
        self.assertIn("tus datos personales se quedan", r)
        hist = [{"role": "assistant", "content": r}]
        self.assertIn("borré 1 recuerdo de", pk("sí, borra el historial", hist))
        self.assertEqual(len(M.hechos()), 3)

    def test_no_secuestra_otros_borrados(self):
        for f in ["borra todo el contenido del archivo mundo", "borra la última línea del archivo mundo",
                  "elimina el archivo mundo", "borra el chat", "olvida el tema, mejor dime la hora"]:
            r = pk(f)
            self.assertTrue(r is None or "Olvidé" in r or "No tengo guardado" in r or "¿Qué quieres" in r, (f, r))
        self.assertEqual(len(M.hechos()), 3)

    def test_pausa_y_reactivar(self):
        self.assertIn("Memoria en pausa", pk("desactiva la memoria"))
        self.assertEqual(M.auto_guardar("vivo en Metapán"), [])
        self.assertFalse(M.registrar("c", "qué es la deflación en economía", "Es la baja...", "documentos"))
        self.assertIn("activada", pk("activa la memoria"))
        self.assertTrue(M.registrar("c", "qué es la deflación en economía", "Es la baja...", "documentos"))


class Archivo(Base):
    def test_persistencia_y_atomico(self):
        M.agregar_hecho("Nombre: Ana", clave="nombre")
        M._cache.update(mtime=None, datos=None)                 # como tras reiniciar PK
        self.assertEqual(M.hechos()[0]["texto"], "Nombre: Ana")
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".tmp")], [])

    def test_archivo_roto_no_tumba_a_pk(self):
        with open(os.path.join(self.dir, "memoria.json"), "w", encoding="utf-8") as f:
            f.write("{esto no es json")
        self.assertEqual(M.hechos(), [])
        M.agregar_hecho("Nombre: Ana")                          # y se puede seguir usando
        self.assertEqual(len(M.hechos()), 1)

    def test_editar_y_borrar(self):
        h, _ = M.agregar_hecho("Nombre: Ana", clave="nombre")
        self.assertTrue(M.editar_hecho(h["id"], "Nombre: Ana María"))
        self.assertFalse(M.editar_hecho(h["id"], "mi contraseña es 123"))
        self.assertEqual(M.hechos()[0]["texto"], "Nombre: Ana María")
        self.assertTrue(M.borrar_hecho(h["id"]))
        self.assertFalse(M.borrar_hecho(h["id"]))

    def test_instantanea(self):
        M.agregar_hecho("Nombre: Ana")
        M.registrar("c", "qué es la inflación en economía", "Es el aumento", "documentos")
        s = M.instantanea()
        self.assertEqual((len(s["hechos"]), len(s["episodios"])), (1, 1))
        self.assertEqual(set(s["config"]), {"hechos_auto", "historial", "usar"})


if __name__ == "__main__":
    unittest.main()
