"""Pruebas de la calculadora y del reloj. Ejecutar:  python -m unittest discover -s tests -v"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import calculadora, reloj  # noqa: E402


def calc(txt):
    r = calculadora.handle(txt)
    return r["message"] if r else None


class Calculadora(unittest.TestCase):
    def test_basicas(self):
        self.assertEqual(calc("cuánto es 25 por 4"), "25 × 4 = 100")
        self.assertEqual(calc("¿Cuánto es 25 x 4?"), "25 × 4 = 100")
        self.assertEqual(calc("(3+5)*2"), "(3 + 5) × 2 = 16")
        self.assertEqual(calc("3 + 4 * 2"), "3 + 4 × 2 = 11")        # precedencia
        self.assertEqual(calc("cuánto es 7 menos 10"), "7 - 10 = -3")
        self.assertEqual(calc("cuánto es -5 + 3"), "-5 + 3 = -2")
        self.assertEqual(calc("dame el resultado de 8 por 8"), "8 × 8 = 64")

    def test_exactitud(self):
        self.assertEqual(calc("cuánto es 0.1 + 0.2"), "0.1 + 0.2 = 0.3")
        self.assertEqual(calc("cuánto es 10 entre 3"), "10 ÷ 3 = 3.3333333333")
        self.assertIn("1,024", calc("2 elevado a 10"))
        self.assertIn("= 8", calc("2 ** 3"))

    def test_porcentajes(self):
        self.assertEqual(calc("15% de 200"), "15% de 200 = 30")
        self.assertEqual(calc("cuánto es el 15% de 200"), "15% de 200 = 30")
        self.assertEqual(calc("100 más el 15%"), "100 + 15% = 115")
        self.assertEqual(calc("100 menos 15%"), "100 - 15% = 85")
        self.assertEqual(calc("qué porcentaje es 30 de 200"), "30 es el 15% de 200")
        self.assertEqual(calc("30 es qué porcentaje de 200"), "30 es el 15% de 200")
        self.assertEqual(calc("9 por ciento de 50"), "9% de 50 = 4.5")

    def test_raices_potencias(self):
        self.assertEqual(calc("raíz cuadrada de 144"), "√144 = 12")
        self.assertEqual(calc("raíz de 2"), "√2 = 1.4142135624")
        self.assertEqual(calc("la raíz de 16 más 3"), "√16 + 3 = 7")
        self.assertEqual(calc("5 al cuadrado"), "5² = 25")
        self.assertEqual(calc("factorial de 5"), "factorial de 5 = 120")
        self.assertEqual(calc("5!"), "5! = 120")
        self.assertEqual(calc("cuánto es la mitad de 50"), "la mitad de 50 = 25")

    def test_palabras(self):
        self.assertEqual(calc("cinco más tres"), "5 + 3 = 8")
        self.assertEqual(calc("veinticinco por cuatro"), "25 × 4 = 100")
        self.assertEqual(calc("treinta y cinco más uno"), "35 + 1 = 36")
        self.assertEqual(calc("dos mil quinientos más trescientos"), "2,500 + 300 = 2,800")
        self.assertEqual(calc("un millón por dos"), "1,000,000 × 2 = 2,000,000")

    def test_formatos_de_numero(self):
        self.assertEqual(calc("cuánto es 1,000,000 por 3"), "1,000,000 × 3 = 3,000,000")
        self.assertEqual(calc("cuánto es 1.500,50 + 20"), "1,500.5 + 20 = 1,520.5")
        self.assertEqual(calc("cuánto es 3,5 por 2"), "3.5 × 2 = 7")

    def test_errores_claros(self):
        self.assertEqual(calc("10/0"), "No se puede dividir entre cero.")
        self.assertIn("raíz", calc("cuánto es raíz de -4").lower())
        self.assertIn("demasiado grande", calc("cuanto es 2 elevado a 5000"))
        self.assertIn("No pude entender", calc("calcula 3 +"))

    def test_no_es_cuenta_deja_pasar(self):
        for frase in ["hola", "tengo 5 más 3 manzanas", "quiero 5 manzanas", "2024", "5%",
                      "en 2020 pasó algo", "¿quién es Billie Joe Armstrong?",
                      "crea un archivo llamado mundo", "cuánto cuesta una laptop",
                      "dame 3 ideas para un proyecto", "háblame de la segunda guerra mundial",
                      "qué es una raíz cuadrada", "el número 5 por favor"]:
            self.assertIsNone(calc(frase), frase)

    def test_nunca_ejecuta_codigo(self):
        for peligro in ["cuánto es __import__('os').system('dir')", "calcula open('x')",
                        "cuánto es 2 ** 99999999", "9**9**9**9", "cuánto es (1)" + "(" * 50]:
            r = calculadora.handle(peligro)
            self.assertTrue(r is None or isinstance(r["message"], str))


class FakeReloj(unittest.TestCase):
    """Hora fija: miércoles 28 de octubre de 2026, 23:34 en El Salvador (UTC-6)."""

    def setUp(self):
        self.utc = datetime(2026, 10, 29, 5, 34, tzinfo=timezone.utc)
        self._ahora = reloj.ahora
        sv = reloj._zona("America/El_Salvador")

        def falso(nombre_zona=None):
            z = reloj._zona(nombre_zona) if nombre_zona else sv
            return self.utc.astimezone(z)
        reloj.ahora = falso
        reloj.hoy = lambda: falso().date()

    def tearDown(self):
        reloj.ahora = self._ahora
        reloj.hoy = lambda: reloj.ahora().date()

    def r(self, txt):
        x = reloj.handle(txt)
        return x["message"] if x else None

    def test_hora_y_fecha(self):
        self.assertEqual(self.r("¿qué hora es?"), "Son las 11:34 p. m. (hora de El Salvador). Hoy es miércoles 28 de octubre de 2026.")
        self.assertIn("Son las 11:34 p. m.", self.r("dime la hora"))
        self.assertIn("miércoles 28 de octubre de 2026", self.r("qué hora es"))
        self.assertEqual(self.r("¿Qué día es hoy?"), "Hoy es miércoles 28 de octubre de 2026.")
        self.assertEqual(self.r("¿a cuántos estamos?"), "Hoy es miércoles 28 de octubre de 2026.")

    def test_otras_ciudades(self):
        self.assertIn("En Tokio son las 2:34 p. m. de mañana", self.r("¿qué hora es en Tokio?"))
        self.assertIn("En Madrid son las 6:34 a. m.", self.r("qué hora es en Madrid"))
        self.assertIn("En Nueva York es la 1:34 a. m. de mañana", self.r("qué hora es en Nueva York"))
        self.assertIn("No conozco", self.r("qué hora es en Narnia"))

    def test_dia_de_una_fecha(self):
        self.assertIn("Viernes 25 de diciembre de 2026", self.r("¿qué día cae el 25 de diciembre?"))
        self.assertIn("Lunes 1 de enero de 2029", self.r("qué día será el 1 de enero de 2029"))
        self.assertIn("Mañana", self.r("qué día es mañana"))
        self.assertIn("Ayer fue martes 27 de octubre", self.r("¿qué día fue ayer?"))
        self.assertIn("no existe", self.r("qué día cae el 31 de febrero"))

    def test_cuantos_dias(self):
        self.assertIn("Faltan 58 días para Navidad", self.r("¿cuántos días faltan para Navidad?"))
        self.assertIn("Faltan 65 días para Año Nuevo", self.r("cuántos días faltan para año nuevo"))
        self.assertIn("Han pasado 300 días", self.r("cuántos días han pasado desde el 1 de enero"))
        self.assertIn("hay 365 días", self.r("cuántos días hay entre el 1 de enero de 2027 y el 1 de enero de 2028"))
        self.assertIn("Faltan 2 días", self.r("cuántos días faltan para el viernes"))

    def test_dentro_de(self):
        self.assertIn("viernes 27 de noviembre de 2026", self.r("qué fecha será dentro de 30 días"))
        self.assertIn("jueves 28 de enero de 2027", self.r("qué fecha será dentro de 3 meses"))
        self.assertIn("miércoles 14 de octubre de 2026", self.r("qué fecha fue hace 2 semanas"))

    def test_no_secuestra_otras_preguntas(self):
        for frase in ["hola", "¿a qué hora abre el banco?", "¿quién fue Napoleón?",
                      "cuéntame de la hora del té", "qué día nació Messi", "crea un archivo llamado hoy",
                      "dame una biografía de Sonic the hedgehog"]:
            self.assertIsNone(self.r(frase), frase)

    def test_contexto_para_el_modelo(self):
        self.assertIn("miércoles 28 de octubre de 2026", reloj.contexto_actual())


if __name__ == "__main__":
    unittest.main()
