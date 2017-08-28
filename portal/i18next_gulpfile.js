/*
 * prerequisites:
 * nodeJS virtual environment install via pip nodeenv
 * install NPM (node package manager)
 * install all required modules (i.e. run npm install in the directory containing package.json)
 * run gulp --gulpfile i18next_gulpfile.js will perform default task -
 * which will perform text extraction and translate resulting json to pot file
 * run gulp --gulpfile i18next_gulpfile.js [task name]  will run individual task
 * NB:  should NOT run this in Production environment, the resulting modules in node_modules/ folder from running `npm install` should never be checked in
 */
var gulp = require('gulp');
var source = require('vinyl-source-stream');
var request = require('request');
var merge = require('merge2');
var buffer = require('gulp-buffer');
var del = require('del');
var scanner = require('i18next-scanner');
var concatPo = require('gulp-concat-po');
const path = require('path');
const fs = require('fs');
const i18nextConv = require('i18next-conv');
/*
 * where the generated json/pot files from extraction of js files will reside
 */
const translationSourceDir = path.join(__dirname, './translations/js/src/');
/*
 * the path to the converted json file from po file of corresponding locale
 * JS files will consume the translated text from here
 * note json files are saved for each specific locale
 */
const translationDestinationDir = path.join(__dirname,'./static/files/locales/');
/*
 * namespace
 */
const nameSpace = 'frontend';
const srcPotFileName = translationSourceDir+nameSpace+'.pot';

/*
 * helper function for writing file
 */
function save(target) {
  return result => {
    fs.writeFileSync(target, result);
  };
};

/*
 * extracting text from js/html files into json file
 */
gulp.task('i18next-extraction', ['clean-src'], function() {
    console.log('extracting text and generate json file ...');
    return gulp.src(['static/**/*.{js,html}'])
               .pipe(scanner({
                    keySeparator: "|",
                    nsSeparator: "|",
                    attr: {
                        list: ['data-i18n'],
                        extensions: ['.js', '.html', '.htm']
                    },
                    func: {
                        list: ['i18next.t', 'i18n.t'],
                        extensions: ['.js', '.jsx']
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: './src/' + nameSpace + '.json'
                    }
                }))
              .pipe(gulp.dest('translations/js'));
});

/*
 * convert json to pot (the definition file) for translator's consumption
 */
gulp.task('i18nextConvertJSONToPOT', ['i18next-extraction'], function() {

    const options = {/* you options here */}
   /*
    * converting json to pot
    */
    console.log('converting JSON to POT...');
    i18nextConv.i18nextToPot('en', fs.readFileSync(translationSourceDir+nameSpace+'.json'), options).then(save(srcPotFileName));

});

/*
 * combine newly created pot file to existing messages.pot file ???
 * do we need this step??
 */
gulp.task('combineAllPotFiles', ['i18nextConvertJSONToPOT'], function() {
    console.log("combine all pot files ...")
    return gulp.src([srcPotFileName, 'translations/messages.pot'])
          .pipe(concatPo('messages.pot'))
          .pipe(gulp.dest('translations'));
});

/*
 * converting po to json files
 * note translating existing po file to json, which will be consumed by the front end
 * this task assumes that:
 *    1. text has been extracted from js file into JSON file
 *    2. translated JSON into POT
 *    3. merged new POT into main POT file [need to check about this step]
 *    4. Po files have been returned from translator after uploading POT file from #3
 */
gulp.task('i18nextConvertPOToJSON', ['clean-dest'], function() {
  console.log('converting po to json ...');
  const options = {/* you options here */}
   /*
    * translating po file to json for supported languages
    */
  var __path = path.join(__dirname,'./translations');
  fs.readdir(__path, function(err, files) {
      files.forEach(function(file) {
          let filePath = __path + '/' + file;
          fs.stat(filePath, function(err, stat) {
              if (stat.isDirectory()) {
                /*
                 * directories are EN_US, EN_AU, etc.
                 * so check to see if each has a PO file
                 */
                let poFilePath = __path + '/' + file + '/LC_MESSAGES/messages.po';
                if (fs.existsSync(poFilePath)) {
                    let destDir = translationDestinationDir+file.replace('_', '-');
                    console.log('locale found: ' + file);
                    if (!fs.existsSync(destDir)){
                      fs.mkdirSync(destDir);
                    };
                    /*
                     * write corresponding json file from each po file
                     */
                    i18nextConv.gettextToI18next(file, fs.readFileSync(poFilePath), false)
                    .then(save(destDir+'/translation.json'));
                };
              };
          });
      });
  });
});

/*
 * clean all generated source files
 */
gulp.task('clean-src', function() {
  del([translationSourceDir + '*']);
});

/*
 * clean all generated destination json files
 */
gulp.task('clean-dest', function() {
  del([translationDestinationDir + '*/translation.json']);
});


/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have
   it return the po files
   so probably should run 'i18nextConvertPOToJSON' task separately
 */
gulp.task('default', ['i18nextConvertJSONToPOT'], function() {
    console.log('running default task..');
});