const webpack = require("webpack");
const path = require("path");
const TerserWebpackPlugin = require("terser-webpack-plugin");
const OptimizeCssAssetsPlugin = require("optimize-css-assets-webpack-plugin");
const HtmlWebpackPlugin = require('html-webpack-plugin');
const vendorPath = './src/vendors';
const VueLoaderPlugin = require("vue-loader/lib/plugin");
module.exports = function(_env, argv) {
  const isProduction = argv.mode === "production";
  const isDevelopment = !isProduction;
  /*
   * output to static file for ease of development
   */
  const rootDirectory = isDevelopment?"../static":"/dist";
  const outputDirectory = rootDirectory+"/bundle";
  const templateDirectory = `${rootDirectory}/templates`;
  return {
    entry:  ['whatwg-fetch', path.join(__dirname, './src/app.js')],
    watchOptions: {
      aggregateTimeout: 300,
      poll: 1000
    },
    output: {
      path: path.join(__dirname, outputDirectory),
      /*
       * create a new hash for each new build
       */
      filename: `app.bundle.[name]${isProduction?'-[hash:6]':''}.js`,
      publicPath: "/static/bundle/"
    },
    resolve: {
        extensions: ['.js', '.vue'],
        alias: {
          'jquery': path.join(__dirname, '/node_modules/jquery/dist/jquery.min.js')
        }
    },
    module: {
      rules: [
        {
          test: require.resolve('jquery'),
          loader: 'expose-loader',
          options: {
            exposes: ['$', 'jQuery'],
          },
        },
        {
          test: /\.woff2?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
          use: 'url-loader?limit=10000',
        },
        {
          test: /\.(ttf|eot|svg)(\?[\s\S]+)?$/,
          use: 'file-loader',
        },
        {
          test: /\.(js)$/,
          exclude: [/node_modules/, path.resolve(__dirname, vendorPath)],
          loader: 'babel-loader',
          query: {
            presets: [
              ['@babel/preset-env'],
            ],
          },
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader']
        },
        {
          test: /\.less$/,
          use: [
            {
              loader: 'style-loader', // creates style nodes from JS strings
            },
            {
              loader: 'css-loader', // translates CSS into CommonJS
              options: {
                sourceMap: isDevelopment ? true: false
              }
            },
            {
              loader: 'less-loader', // compiles Less to CSS
              options: {
                sourceMap: isDevelopment ? true: false
              },
            },
          ],
        },
        {
          test: /\.vue$/,
          use: 'vue-loader'
        }
      ],
    },
    plugins: [
      new VueLoaderPlugin(),
      //new CleanWebpackPlugin(),
      new HtmlWebpackPlugin({
        title: "Substudy Domains",
        template: path.join(__dirname, '/src/app.html'),
        filename: path.join(__dirname, `${templateDirectory}/substudy_domains.html`),
        favicon: path.join(__dirname, '/src/assets/favicon.ico'),
      }),
      new webpack.ProvidePlugin(
        { 
          Promise: 'es6-promise',
          $: 'jquery',
          jquery: 'jquery',
          jQuery: 'jquery',
          'window.jQuery': 'jquery',
          Vue: ['vue/dist/vue.esm.js', 'default'],
        }
      ),
      new webpack.DefinePlugin({
        "process.env.NODE_ENV": JSON.stringify(
          isProduction ? "production" : "development"
        )
      })
    ],
    optimization: {
      minimize: isProduction,
      minimizer: [
        new TerserWebpackPlugin({
          terserOptions: {
            compress: {
              comparisons: false
            },
            mangle: {
              safari10: true
            },
            output: {
              comments: false,
              ascii_only: true
            },
            sourceMap: !isProduction,
            warnings: false
          }
        }),
        new OptimizeCssAssetsPlugin({
          verbose: true
        }),
      ],
      splitChunks: {
        chunks: "all",
        minSize: 0,
        maxInitialRequests: 10,
        maxAsyncRequests: 10,
        cacheGroups: {
          vendors: {
            test: /[\\/]node_modules[\\/]/,
            name(module, chunks, cacheGroupKey) {
              const packageName = module.context.match(
                /[\\/]node_modules[\\/](.*?)([\\/]|$)/
              )[1];
              return `${cacheGroupKey}.${packageName.replace("@", "")}`;
            }
          },
          common: {
            minChunks: 2,
            priority: -10
          }
        }
      }
    }
  };
};
