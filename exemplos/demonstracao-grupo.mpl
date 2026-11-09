funcao inteiro mdc(inteiro a, inteiro b) {
  se (b == 0) {
    retorne a;
  }
  retorne mdc(b, a % b);
}

funcao real montante(real capital, real taxa, inteiro meses) {
  inteiro mes = 0;
  enquanto (mes < meses) {
    capital = capital * (1.0 + taxa);
    mes = mes + 1;
  }
  retorne capital;
}

funcao vazio principal() {
  escreva("Demonstracao da MPL");
  escreva("MDC de 84 e 30:");
  escreva(mdc(84, 30));
  escreva("Montante de 1000 a 1,5% por 12 meses:");
  escreva(montante(1000, 0.015, 12));
}
