const assert = require('assert');
const fs = require('fs');
const path = require('path');

const templatePath = path.join(__dirname, 'app', 'templates', 'widgets_config.html');
const source = fs.readFileSync(templatePath, 'utf8');

function expectRegex(regex, message) {
  assert(regex.test(source), message);
}

function run() {
  assert(!/<body class="compact">/.test(source), 'Tela de configuracao deve iniciar expandida');
  expectRegex(/<div class="hero-overview">/m, 'Hero deve expor cards de orientacao');
  expectRegex(/let\s+showHelp\s*=\s*true;/m, 'Ajuda deve ser visivel por padrao');
  assert(!source.includes('settings-category-body" hidden'), 'Secoes principais nao devem iniciar ocultas');

  console.log('✓ Guard test: configuracao inicia em layout expandido e com orientacao explicita.');
}

run();
