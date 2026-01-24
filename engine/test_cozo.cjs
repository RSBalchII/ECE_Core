
try {
    console.log('Requiring cozo-node...');
    const cozo = require('cozo-node');
    console.log('SUCCESS: cozo-node loaded', cozo);
} catch (e) {
    console.error('FAIL: require(cozo-node) failed');
    console.error(e);
}
