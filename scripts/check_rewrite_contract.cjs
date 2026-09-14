const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const root = path.resolve(__dirname, '..')
const project = path.join(root, 'utils/powerlifting-app')
const ts = require(path.join(project, 'node_modules/typescript'))
const directory = path.join(project, 'services/operations')
const files = fs.readdirSync(directory).filter(file => file.endsWith('.json'))
assert.equal(files.length, 16)
const operations = new Map()
for (const file of files) {
  for (const operation of JSON.parse(fs.readFileSync(path.join(directory, file), 'utf8'))) {
    assert(!operations.has(operation.name), `Duplicate ${operation.name}`)
    assert.equal(operation.domain, file.slice(0, -5))
    operations.set(operation.name, { name: operation.name, domain: operation.domain, handler: operation.handler, legacy: operation.legacy, callers: [] })
  }
}
const missing = []
function visitFile(file) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true)
  function visit(node) {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && ['invokeLambda', 'invokeToolDirect', 'invokeAnalyticsOperation'].includes(node.expression.text)) {
      const first = node.arguments[0]
      if (first && ts.isStringLiteral(first)) {
        let operation = first.text
        const arguments = node.arguments[1]
        if (arguments && ts.isObjectLiteralExpression(arguments)) {
          const selector = arguments.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText(source).replace(/['"]/g, '') === 'function')
          if (selector && ts.isStringLiteral(selector.initializer)) operation = selector.initializer.text
          else if (selector) { ts.forEachChild(node, visit); return }
        }
        const caller = { path: path.relative(root, file), line: source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1 }
        if (operations.has(operation)) operations.get(operation).callers.push(caller)
        else missing.push({ operation, ...caller })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
}
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name)
    if (entry.isDirectory()) walk(file)
    else if (entry.name.endsWith('.ts') && !entry.name.endsWith('.test.ts')) visitFile(file)
  }
}
walk(path.join(project, 'backend/src'))
assert.deepEqual(missing, [], 'Unregistered literal domain callers')
fs.writeFileSync(path.join(root, 'docs/contracts/operation-callers.json'), JSON.stringify([...operations.values()], null, 2) + '\n')
console.log(`PASS ${files.length} domains, ${operations.size} operations, ${[...operations.values()].reduce((sum, operation) => sum + operation.callers.length, 0)} registered literal backend callers`)
