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
var {series, src, dest} = require("gulp");
var del = require("del");
var scanner = require("i18next-scanner");
var merge_json = require("gulp-merge-json");
var using = require("gulp-using");
const path = require("path");
const fs = require("fs");
const i18nextConv = require("i18next-conv");
/*
 * where the generated json/pot files from extraction of js files will reside
 */
const translationSourceDir = path.join(__dirname, "./translations/js/src/");
/*
 * the path to the converted json file from po file of corresponding locale
 * JS files will consume the translated text from here
 * note json files are saved for each specific locale
 */
const translationDestinationDir = path.join(__dirname,"./static/files/locales/");

/*
 * namespace
 */
const nameSpace = "frontend";
const epromsNameSpace = "eproms";
const truenthNameSpace = "gil";
const srcPotFileName = translationSourceDir+nameSpace+".pot";
const epromsSrcPotFileName =  translationSourceDir+epromsNameSpace+".pot";
const truenthSrcPotFileName = translationSourceDir+truenthNameSpace+".pot";

/*
 * helper function for writing file
 */
function save(target) {
  return result => {
    fs.writeFileSync(target, result);
  };
};

/*
 * i18next scanner helper function
 */
function i18nextScanner(files, outputFileName) {
  return src(files)
               .pipe(scanner({
                    keySeparator: "|",
                    nsSeparator: "|",
                    attr: {
                        list: ["data-i18n"],
                        extensions: [".js", ".html", ".htm"]
                    },
                    func: {
                        list: ["i18next.t", "i18n.t"],
                        extensions: [".js", ".jsx", ".html", ".htm"]
                    },
                    resource: {
                        //the source path is relative to current working directory as specified in the destination folder
                        savePath: outputFileName
                    },
                    interpolation: {
                        prefix: "{",
                        suffix: "}"
                    }
                }))
              .pipe(dest("translations/js"));
};

/*
 * helper function for writing json file from source po file to specified destination
 */
function writeJsonFileFromPoFile(locale, messageFilePath, outputFileName) {
  let existed = fs.existsSync(messageFilePath);
  if (existed) {
    /*
     * write corresponding json file from source po file
     */
    try {
      console.log("source file, " + messageFilePath + ", found for locale: ", locale, " outputFileName:", outputFileName);
      i18nextConv.gettextToI18next(locale, fs.readFileSync(messageFilePath), false)
      .then(save(outputFileName));
    } catch(e) {
      console.log("Error occurred writing json from po file: ", messageFilePath);
    }
  }
};

/*
 * clean eproms source json file
 */
const cleanEpromsSrc = function(callback) {
  console.log("delete EPROMS source JSON file...");
  del([translationSourceDir + epromsNameSpace + ".json"]);
  callback();
};
exports.cleanEpromsSrc = series(cleanEpromsSrc);
/*
 * clean Truenth source json file
 */
const cleanTruenthSrc = function(callback) {
  console.log("Delete TRUEnth source JSON file...");
  del([translationSourceDir + truenthNameSpace + ".json"]);
  callback();
};
exports.cleanTruenthSrc = series(cleanTruenthSrc);
/*
 * clean common source file
 */
const cleanSrc = function(callback) {
  console.log("Deleting json files in source directory...");
  del([translationSourceDir + nameSpace + ".json"]);
  callback();
};
exports.cleanSrc = series(cleanSrc);

/*
 * clean all generated destination json files
 */
const cleanDest = function(callback) {
  console.log("Deleting json files in destination directory...");
  del([translationDestinationDir + "*/*.json"]);
  callback();
};
exports.cleanDest = series(cleanDest);

/*
 * extracting text from common js/html files into json file
 */
const i18nextExtraction = function(callback) {
  console.log("Extracting i18next strings from JS and HTML template files...");
  i18nextScanner(["static/**/*.{js,html}", "templates/*.html"], "./src/" + nameSpace + ".json");
  callback();
}
exports.i18nextExtraction = series(cleanSrc, i18nextExtraction);


/*
 * extracting text from  Eproms html files into json file
 */
const i18nextExtractionEproms = function(callback) {
  console.log("Extracting i18next strings and generate EPROMS source json file ...");
  i18nextScanner(["eproms/templates/eproms/*.html"], "./src/" + epromsNameSpace + ".json");
  callback();
};
exports.i18nextExtractionEproms = series(cleanEpromsSrc, i18nextExtractionEproms);


/*
 * extracting text from TrueNTH html files into json file
 */
const i18nextExtractionTruenth = function(callback) {
  console.log("extracting i18next strings and generating TRUENTH source json file ...");
  i18nextScanner(["gil/templates/gil/*.html"], "./src/" + truenthNameSpace + ".json");
  callback();
};
exports.i18nextExtractionTruenth = series(cleanTruenthSrc, i18nextExtractionTruenth);

/*
 * convert eproms json to pot (the definition file) for translator's consumption
 */
const i18nextConvertEpromsJSONToPOT = function(callback) {
  console.log("Converting EPROMS JSON source file to POT file...");
  i18nextConv.i18nextToPot("en", fs.readFileSync(translationSourceDir+epromsNameSpace+".json"), options).then(function() {
    save(epromsSrcPotFileName);
    callback();
  });
};
exports.i18nextConvertEpromsJSONToPOT = series(i18nextExtractionEproms, i18nextConvertEpromsJSONToPOT);
/*
 * convert TrueNTH json to pot (the definition file) for translator's consumption
 */
const i18nextConvertTruenthJSONToPOT = function(callback) {
  options = {
    /*
    specify options here */
  };
  console.log("Converting GIL JSON source file to POT file...");
  i18nextConv.i18nextToPot("en", fs.readFileSync(translationSourceDir+truenthNameSpace+".json"), options).then(function() {
    save(truenthSrcPotFileName);
    callback();
  });
};
exports.i18nextConvertTruenthJSONToPOT = series(i18nextExtractionTruenth, i18nextConvertTruenthJSONToPOT);

/*
 * convert common json file to pot (the definition file) for translator's consumption
 */
const i18nextConvertJSONToPOT = function(callback) {
  options = {
    /*
    specify options here */
  };
  console.log("Converting common JSON source file to POT file...");
  i18nextConv.i18nextToPot("en", fs.readFileSync(translationSourceDir+nameSpace+".json"), options).then(function() {
    save(srcPotFileName);
    callback();
  });
};
exports.i18nextConvertJSONToPOT = series(i18nextExtraction, i18nextConvertJSONToPOT);

/*
 * converting po to json files
 * note translating existing po file to json, which will be consumed by the front end
 * this task assumes that:
 *    1. text has been extracted from js file into JSON file
 *    2. translated JSON into POT
 *    3. Po files have been returned from translator after uploading POT file from #2
 */
const i18nextConvertPOToJSON = function(callback) {
  console.log("Converting PO files to destination JSON files ...");
  const options = {/* you options here */};
   /*
    * translating po file to json for supported languages
    */
  var __path = path.join(__dirname,"./translations");
  fs.readdir(__path, function(err, files) {
      files.forEach(function(file) {
        //skip js directory - as it contains original translation json file
        if (file.toLowerCase() !== "js") {
          let filePath = __path + "/" + file;
          fs.stat(filePath, function(err, stat) {
              if (stat.isDirectory()) {
                /*
                 * directories are EN_US, EN_AU, etc.
                 * so check to see if each has a PO file
                 */
                let destDir = translationDestinationDir+(file.replace("_", "-"));

                if (!fs.existsSync(destDir)){
                  fs.mkdirSync(destDir);
                };

                ["messages", "frontend", "eproms", "gil"].forEach(function(source) {
                    /*
                     * write corresponding json file from each po file
                     */
                    writeJsonFileFromPoFile(file, __path+"/"+file+"/LC_MESSAGES/"+source+".po", destDir+"/"+source+".json");
                });
              };
          });
        }
      });
  });
  callback();
};
exports.i18nextConvertPOToJSON = series(i18nextConvertPOToJSON);

/*
 * combining each json file in each locale folder into one file, namely, the translation.json file, to be consumed by the frontend
 * NOTE this task will need to be run after i18nextConvertPOToJSON task, which creates json files from po files
 */
const combineTranslationJsons = function(callback) {
  console.log("Combining JSON files in each destination directory ...");
  const options = {/* you options here */};
   /*
    * translating po file to json for supported languages
    */
  var __path = path.join(__dirname,"./translations");
  fs.readdir(__path, function(err, files) {
      files.forEach(function(file) {
          let filePath = __path + "/" + file;
          fs.stat(filePath, function(err, stat) {
              if (stat.isDirectory()) {
                /*
                 * directories are EN_US, EN_AU, etc.
                 */
                let destDir = translationDestinationDir+(file.replace("_", "-"));

                /*
                 * merge json files into one for frontend to consume
                 * note this plug-in will remove duplicate entries
                 * not this will not delete the original json files that were merged
                 */
                  console.log("merge destination json files...");
                  console.log("destination directory: " + destDir);
                  try {
                    src(destDir +"/*.json")
                      .pipe(using())
                      .pipe(merge_json({
                        fileName: "translation.json"
                      }))
                      .pipe(dest(destDir));
                  } catch(e) {
                    console.log("Error occurred merging files " + e.message);
                  };

              };
          });
      });
  });
  callback();
};
exports.combineTranslationJsons = series(combineTranslationJsons);
//convert EPROMS source json file to POT file
exports.eproms = series(i18nextConvertEpromsJSONToPOT);
//convert GIL source json file to POT file
exports.gil = series(i18nextConvertTruenthJSONToPOT);
/*
 * NOTE, the task - converting po to json file is not included, as I think we need to upload pot to smartling first to have
   it return the po files
   so probably should run "i18nextConvertPOToJSON" task separately
 */
exports.default = series(i18nextConvertJSONToPOT);

