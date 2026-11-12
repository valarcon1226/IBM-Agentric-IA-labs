import path from 'path';
import fs from 'fs';
import newman from 'newman';

const reportsDir = path.resolve(process.cwd(), 'reports');
if (!fs.existsSync(reportsDir)) {
  fs.mkdirSync(reportsDir, { recursive: true });
}

const collectionPath = path.resolve(process.cwd(), 'postman/petstore-v3.collection.json');
const junitReportPath = path.resolve(reportsDir, 'newman-junit.xml');

console.log(`Starting Newman execution against Petstore v3...`);
console.log(`Collection: ${collectionPath}`);
console.log(`JUnit Report Target: ${junitReportPath}`);

newman.run(
  {
    collection: collectionPath,
    reporters: ['cli', 'junit'],
    reporter: {
      junit: {
        export: junitReportPath,
      },
    },
  },
  (err, summary) => {
    if (err) {
      console.error('[ERROR] Newman run failed with error:', err);
      process.exit(1);
    }

    const failures = summary.run.failures;
    console.log('--------------------------------------------------');
    console.log(`NEWMAN EXECUTION COMPLETE:`);
    console.log(`Total Requests:    ${summary.run.stats.requests.total}`);
    console.log(`Total Assertions:  ${summary.run.stats.assertions.total}`);
    console.log(`Failed Assertions: ${summary.run.stats.assertions.failed}`);
    console.log(`JUnit XML saved to: ${junitReportPath}`);
    console.log('--------------------------------------------------');

    if (failures.length > 0) {
      console.error(`[ERROR] ${failures.length} assertion(s) failed in Newman test run.`);
      process.exit(1);
    } else {
      console.log('[OK] All Petstore v3 Postman tests passed successfully.');
    }
  },
);
