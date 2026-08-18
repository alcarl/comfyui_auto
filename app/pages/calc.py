import flet as ft

from app.base import BasePage


class CalcButton(ft.ElevatedButton):
    def __init__(self, text, button_clicked, expand=1):
        super().__init__()
        self.text = text
        self.expand = expand
        self.on_click = button_clicked
        self.data = text


class DigitButton(CalcButton):
    def __init__(self, text, button_clicked, expand=1):
        CalcButton.__init__(self, text, button_clicked, expand)
        self.bgcolor = ft.Colors.WHITE24
        self.color = ft.Colors.WHITE


class ActionButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.ORANGE
        self.color = ft.Colors.WHITE


class ExtraActionButton(CalcButton):
    def __init__(self, text, button_clicked):
        CalcButton.__init__(self, text, button_clicked)
        self.bgcolor = ft.Colors.BLUE_GREY_100
        self.color = ft.Colors.BLACK


class CalculatorApp(ft.Container):
    def __init__(self):
        super().__init__()

        # 用于显示完整计算过程和结果
        self.formula = ft.Text(value="", color=ft.Colors.WHITE, size=16)  # 公式显示
        self.result = ft.Text(value="0", color=ft.Colors.WHITE, size=24)  # 结果显示
        
        self.reset()

        self.width = 500
        self.bgcolor = ft.Colors.BLACK
        self.border_radius = ft.border_radius.all(20)
        self.padding = 20
        self.content = ft.Column(
            controls=[
                ft.Row(controls=[self.formula], alignment="end"),  # 显示公式
                ft.Row(controls=[self.result], alignment="end"),  # 显示结果
                ft.Row(
                    controls=[
                        ExtraActionButton(
                            text="AC", button_clicked=self.button_clicked
                        ),
                        ExtraActionButton(
                            text="+/-", button_clicked=self.button_clicked
                        ),
                        ExtraActionButton(text="%", button_clicked=self.button_clicked),
                        ActionButton(text="/", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        DigitButton(text="7", button_clicked=self.button_clicked),
                        DigitButton(text="8", button_clicked=self.button_clicked),
                        DigitButton(text="9", button_clicked=self.button_clicked),
                        ActionButton(text="*", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        DigitButton(text="4", button_clicked=self.button_clicked),
                        DigitButton(text="5", button_clicked=self.button_clicked),
                        DigitButton(text="6", button_clicked=self.button_clicked),
                        ActionButton(text="-", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        DigitButton(text="1", button_clicked=self.button_clicked),
                        DigitButton(text="2", button_clicked=self.button_clicked),
                        DigitButton(text="3", button_clicked=self.button_clicked),
                        ActionButton(text="+", button_clicked=self.button_clicked),
                    ]
                ),
                ft.Row(
                    controls=[
                        DigitButton(
                            text="0", expand=2, button_clicked=self.button_clicked
                        ),
                        DigitButton(text=".", button_clicked=self.button_clicked),
                        ActionButton(text="=", button_clicked=self.button_clicked),
                    ]
                ),
                ft.TextButton("访问 文档", icon=ft.Icons.OPEN_IN_NEW, url="https://flet.qiannianlu.com/docs/tutorials/python-calculator")
            ],
            spacing=20,
            height=500,
        )

    def button_clicked(self, e):
        data = e.control.data
        print(f"Button clicked with data = {data}")

        if data == "AC":
            self.reset()

        elif data in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "."):
            if self.is_new_calculation:
                self.calculation_history = ""
                self.formula.value = ""
                self.is_new_calculation = False
            if self.result.value == "0" or self.new_operand:
                self.result.value = data
                self.new_operand = False
            else:
                self.result.value += data
            self.calculation_history += data  # 更新计算历史

        elif data in ("+", "-", "*", "/"):
            if not self.new_operand:  # 如果不是新操作，先计算当前结果
                self.result.value = self.calculate(
                    self.operand1, float(self.result.value), self.operator
                )
                self.operand1 = float(self.result.value)
            else:
                self.operand1 = float(self.result.value)
            self.operator = data
            self.calculation_history += f" {data} "  # 更新计算历史
            self.new_operand = True

        elif data == "=":
            result = self.calculate(
                self.operand1, float(self.result.value), self.operator
            )
            # 显示完整计算过程
            self.formula.value = f"{self.calculation_history} = {result}"
            # 只显示最终结果
            self.result.value = str(result)
            # 重置计算状态
            self.operand1 = 0
            self.operator = "+"
            self.new_operand = True
            # 保留完整计算过程
            self.calculation_history = f"{self.calculation_history} = {result}"
            # 标记需要开始新计算
            self.is_new_calculation = True

        elif data == "%":
            self.result.value = str(float(self.result.value) / 100)
            self.calculation_history += " %"
            self.new_operand = True

        elif data == "+/-":
            if self.result.value.startswith("-"):
                self.result.value = self.result.value[1:]
            else:
                self.result.value = "-" + self.result.value
            self.calculation_history += " +/-"

        # 更新公式显示
        self.formula.value = self.calculation_history
        self.update()

    def reset(self):
        self.operator = "+"
        self.operand1 = 0
        self.new_operand = True
        self.calculation_history = ""
        self.result.value = "0"
        self.formula.value = ""
        self.is_new_calculation = True

    def format_number(self, num):
        if num % 1 == 0:
            return int(num)
        return num

    def calculate(self, operand1, operand2, operator):
        try:
            if operator == "+":
                return self.format_number(operand1 + operand2)
            elif operator == "-":
                return self.format_number(operand1 - operand2)
            elif operator == "*":
                return self.format_number(operand1 * operand2)
            elif operator == "/":
                if operand2 == 0:
                    return "Error"
                return self.format_number(operand1 / operand2)
        except Exception as e:
            print(f"Error during calculation: {e}")
            return "Error"


class CalcPage(BasePage):
    def __init__(self, **kwargs):
        super().__init__(title="计算器", **kwargs)
    
    def build_content(self):
        return ft.Row(controls=[CalculatorApp()], alignment=ft.MainAxisAlignment.CENTER)
